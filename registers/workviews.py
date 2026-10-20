from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from assessments.calculations import KEYS, calculate_score
from assessments.services import save_marks, save_rule
from attendance.services import attendance_summaries, eligible, save_attendance
from core.dates import parse_date
from core.errors import DomainError
from core.forms import MutationForm
from django.urls import reverse
from exports.models import ExportRecord
from exports.preview import prepare_booklet_preview
from exports.snapshot import build_export_snapshot, create_export
from registers.entries import apply_paste
from registers.models import Enrollment, LessonPlanRow
from registers.paste import FIELDS, preview_paste
from registers.services import owned_register
from scheduling.models import Holiday, ScheduleConflict, Session, TimetableEntry
from scheduling.services import (
    apply_rebuild,
    preview_rebuild,
    resolve_conflict,
    save_holiday,
    save_session,
    save_slot,
)

from .workforms import (
    HolidayForm,
    LessonForm,
    MarksForm,
    PasteForm,
    RulesForm,
    SessionForm,
    SlotForm,
    StudentForm,
    ThroughForm,
)

TABS = [
    ("students", "Students"),
    ("lessons", "Lessons"),
    ("timetable", "Timetable"),
    ("sessions", "Classes & tests"),
    ("holidays", "Holidays"),
    ("attendance", "Attendance"),
    ("rules", "Assessment rules"),
    ("marks", "Marks"),
    ("exports", "Word exports"),
    ("preview", "Print preview"),
]
EDITORS = {
    "students": (StudentForm, Enrollment),
    "lessons": (LessonForm, LessonPlanRow),
    "timetable": (SlotForm, TimetableEntry),
    "sessions": (SessionForm, Session),
    "holidays": (HolidayForm, Holiday),
}


def token(register, actor, data):
    return signing.dumps(
        {"register": str(register.pk), "actor": actor.pk, "data": data},
        salt="entry-preview",
        compress=True,
    )


def untoken(value, register, actor):
    try:
        content = signing.loads(value, salt="entry-preview", max_age=1800)
        if content["register"] != str(register.pk) or content["actor"] != actor.pk:
            raise ValueError
        return content["data"]
    except (signing.BadSignature, ValueError, KeyError):
        raise DomainError(
            "This preview expired or does not belong to this register. Preview again."
        ) from None


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def workspace(request, register_id, tab):
    register = owned_register(request.user, register_id)
    if tab not in dict(TABS):
        from django.http import Http404

        raise Http404
    action = request.POST.get("action", "save")
    operation = MutationForm(request.POST or None, revision=register.revision)
    context = {
        "register": register,
        "tab": tab,
        "tabs": TABS,
        "title": dict(TABS)[tab],
        "operation": operation,
        "today": timezone.localdate(),
        "keys": KEYS,
    }
    form = None
    if tab in EDITORS:
        form_class, model = EDITORS[tab]
        instance = (
            get_object_or_404(model, register=register, pk=request.GET["edit"])
            if request.GET.get("edit")
            else None
        )
        initial = {
            "eligible_from": register.term_start,
            "serial_number": register.students.count() + 1,
            "original_number": register.lessons.count() + 1,
            "effective_from": register.term_start,
            "scheduled_date": timezone.localdate(),
            "start_time": "09:00",
            "end_time": "10:00",
        }
        form = form_class(
            request.POST if request.method == "POST" and action == "save" else None,
            instance=instance,
            register=register,
            revision=register.revision,
            initial=initial,
        )
    elif tab == "rules":
        definition = register.marking_rule.definition if hasattr(register, "marking_rule") else None
        form = RulesForm(request.POST or None, definition=definition, revision=register.revision)
    elif tab == "marks":
        form = MarksForm(
            request.POST if request.method == "POST" and action == "save" else None,
            register=register,
            revision=register.revision,
        )
    elif tab == "exports":
        form = ThroughForm(
            request.POST or None,
            revision=register.revision,
            initial={"through": timezone.localdate()},
        )
    paste = None
    if tab in FIELDS:
        paste = PasteForm(
            request.POST if request.method == "POST" and action == "preview" else None,
            revision=register.revision,
            initial={"columns": ",".join(FIELDS[tab])},
        )
    status = 200
    if request.method == "POST":
        try:
            if register.archived_at:
                raise DomainError("Restore this register before editing it.")
            if action == "preview" and paste and paste.is_valid():
                columns = [c.strip() for c in paste.cleaned_data["columns"].split(",")]
                if len(columns) != len(set(columns)):
                    raise DomainError("Each mapped field must appear once.")
                preview = preview_paste(
                    paste.cleaned_data["text"],
                    table=tab,
                    delimiter=paste.cleaned_data["delimiter"],
                    mapping={key: i for i, key in enumerate(columns)},
                )
                context["preview"] = preview
                if not preview["errors"] and preview["rows"]:
                    context["preview_token"] = token(
                        register,
                        request.user,
                        {
                            "table": tab,
                            "rows": preview["rows"],
                            "expected_revision": paste.cleaned_data["expected_revision"],
                            "request_id": str(paste.cleaned_data["request_id"]),
                        },
                    )
            elif action == "apply_paste":
                data = untoken(request.POST.get("preview_token"), register, request.user)
                if data.pop("table") != tab:
                    raise DomainError("Preview table does not match.")
                service = (
                    save_marks
                    if tab == "marks"
                    else lambda *a, **kw: apply_paste(*a, table=tab, **kw)
                )
                service(request.user, register.pk, **data)
                messages.success(
                    request, "All rows applied. Existing rows not in the paste were kept."
                )
                return redirect("register-workspace", register_id=register.pk, tab=tab)
            elif action == "schedule_preview" and operation.is_valid():
                preview = preview_rebuild(
                    register, effective_from=date.fromisoformat(request.POST["effective_from"])
                )
                context["schedule_preview"] = preview
                context["schedule_token"] = token(
                    register,
                    request.user,
                    {
                        "preview": preview,
                        "expected_revision": operation.cleaned_data["expected_revision"],
                        "request_id": str(operation.cleaned_data["request_id"]),
                    },
                )
            elif action == "schedule_apply":
                data = untoken(request.POST.get("schedule_token"), register, request.user)
                apply_rebuild(request.user, register.pk, **data)
                messages.success(request, "Schedule applied. No attendance was assumed.")
                return redirect("register-workspace", register_id=register.pk, tab="sessions")
            elif action == "resolve" and operation.is_valid():
                resolve_conflict(
                    request.user,
                    register.pk,
                    conflict_id=request.POST.get("conflict_id"),
                    action=request.POST.get("resolution"),
                    reason=request.POST.get("reason", ""),
                    **operation.operation(),
                )
                messages.success(request, "Conflict resolved; recorded attendance was retained.")
                return redirect("register-workspace", register_id=register.pk, tab="holidays")
            elif tab == "attendance" and operation.is_valid():
                cells = [
                    {"enrollment_id": key[5:], "status": value}
                    for key, value in request.POST.items()
                    if key.startswith("cell_")
                ]
                save_attendance(
                    request.user,
                    register.pk,
                    session_id=request.POST.get("session_id"),
                    cells=cells,
                    complete=action == "complete",
                    **operation.operation(),
                )
                messages.success(
                    request,
                    "Attendance saved."
                    if action != "complete"
                    else "Class completed. Eligible unmarked students are now explicitly present.",
                )
                return redirect(request.path + "?session=" + request.POST["session_id"])
            elif action == "save" and form and form.is_valid():
                op = form.operation()
                if tab in ("students", "lessons"):
                    apply_paste(request.user, register.pk, table=tab, rows=[form.values()], **op)
                elif tab in ("timetable", "sessions", "holidays"):
                    service = {
                        "timetable": save_slot,
                        "sessions": save_session,
                        "holidays": save_holiday,
                    }[tab]
                    service(request.user, register.pk, values=form.values(), **op)
                elif tab == "rules":
                    save_rule(request.user, register.pk, definition=form.definition(), **op)
                elif tab == "marks":
                    save_marks(
                        request.user,
                        register.pk,
                        rows=[{key: form.cleaned_data[key] for key in ["usn", *KEYS]}],
                        **op,
                    )
                elif tab == "exports":
                    if form.cleaned_data["through"] > timezone.localdate():
                        raise DomainError("Export cutoff cannot be in the future.")
                    create_export(
                        request.user,
                        register.pk,
                        through=form.cleaned_data["through"],
                        draft=form.cleaned_data["draft"],
                        **op,
                    )
                messages.success(request, "Saved successfully.")
                return redirect("register-workspace", register_id=register.pk, tab=tab)
            else:
                status = 422
        except (DomainError, ValueError, KeyError) as error:
            context["error"] = str(error)
            status = error.status if isinstance(error, DomainError) else 422
            if isinstance(error, DomainError):
                context["error_details"] = error.body.get("field_errors", {})
    context.update(form=form, paste_form=paste)
    if tab == "students":
        context["headings"] = ["Order", "USN", "Name", "Eligible from", "Eligible to"]
        context["rows"] = [
            (str(s.pk), [s.serial_number, s.usn, s.name, s.eligible_from, s.eligible_to or "—"])
            for s in register.students.all()
        ]
    elif tab == "lessons":
        context["headings"] = ["No.", "Topic", "Original date", "Period", "Execution", "Remarks"]
        context["rows"] = [
            (
                str(lesson.pk),
                [
                    lesson.original_number,
                    lesson.topic,
                    lesson.original_date or "—",
                    lesson.original_period,
                    lesson.reported_execution_date or "—",
                    lesson.remarks,
                ],
            )
            for lesson in register.lessons.all()
        ]
    elif tab == "timetable":
        context["headings"] = ["Day", "Period", "From", "Until", "Effective", "Ends"]
        context["rows"] = [
            (
                str(e.pk),
                [
                    e.get_weekday_display(),
                    e.period,
                    e.start_time,
                    e.end_time,
                    e.effective_from,
                    e.effective_to or "Term end",
                ],
            )
            for e in register.timetable_entries.all()
        ]
    elif tab == "sessions":
        context["headings"] = ["Date", "Period", "From", "Until", "Type", "State", "Topic"]
        context["rows"] = [
            (
                str(s.pk),
                [
                    s.date,
                    s.period,
                    s.start_time,
                    s.end_time,
                    f"Test {s.test_number}" if s.kind == "test" else s.get_kind_display(),
                    s.status,
                    s.lesson.topic if s.lesson else "—",
                ],
            )
            for s in register.sessions.select_related("lesson")
        ]
    elif tab == "holidays":
        context["headings"] = ["From", "Until", "Reason"]
        context["rows"] = [
            ("", [h.start_date, h.end_date, h.reason]) for h in register.holidays.all()
        ]
        context["conflicts"] = ScheduleConflict.objects.filter(
            session__register=register, resolved_at__isnull=True
        ).select_related("session", "holiday")
    elif tab == "attendance":
        sessions = sorted(
            register.sessions.exclude(status="cancelled"),
            key=lambda s: (s.date, s.start_time, str(s.pk)),
        )
        summaries = attendance_summaries(register.pk, through=timezone.localdate())
        context["grid_sessions"] = sessions
        context["grid_rows"] = [
            (student, [summaries[str(student.pk)]["sequence"].get(str(s.pk), "") for s in sessions])
            for student in register.students.all()
        ]
        context["sessions"] = sessions
        selected_id = request.GET.get("session") or request.POST.get("session_id")
        selected = (
            next((s for s in sessions if str(s.pk) == selected_id), None)
            if selected_id
            else (sessions[-1] if sessions else None)
        )
        context["selected"] = selected
        context["attendance_rows"] = []
        if selected:
            existing = {e.enrollment_id: e.status for e in selected.attendance.all()}
            for student in register.students.all():
                mark = (
                    existing.get(student.pk, "unmarked")
                    if eligible(student, selected.date)
                    else "not_applicable"
                )
                context["attendance_rows"].append(
                    (
                        student,
                        mark,
                        summaries[str(student.pk)],
                    )
                )
    elif tab == "marks":
        context["headings"] = ["USN", "Name", *KEYS, "Result"]
        context["rows"] = []
        for student in register.students.prefetch_related("marks"):
            marks = {
                m.assessment_key: {"value": m.value, "status": m.status}
                for m in student.marks.all()
            }
            values = [
                "AB"
                if marks.get(k, {}).get("status") == "absent"
                else marks.get(k, {}).get("value", "—")
                for k in KEYS
            ]
            score = (
                calculate_score(register.marking_rule.definition, marks)
                if hasattr(register, "marking_rule")
                else None
            )
            context["rows"].append(
                (
                    "",
                    [
                        student.usn,
                        student.name,
                        *values,
                        score["rounded"] if score and score["status"] == "complete" else "Pending",
                    ],
                )
            )
    elif tab == "exports":
        context["exports"] = register.exports.all().defer("document")
    elif tab == "preview":
        export_records = register.exports.all().defer("document")
        context["exports"] = export_records
        selected_export_id = request.GET.get("export")
        selected_export = None
        if selected_export_id:
            selected_export = export_records.filter(pk=selected_export_id).first()

        through_str = request.GET.get("through")
        through = None
        if through_str:
            try:
                through = parse_date(through_str)
            except Exception:
                through = None

        active_download_url = None
        if selected_export:
            snapshot = selected_export.snapshot
            context["selected_export_id"] = str(selected_export.pk)
            active_download_url = reverse("export-download", args=[selected_export.pk])
            context["preview_through"] = selected_export.snapshot.get("export_date")
        else:
            if not through:
                latest = export_records.first()
                if latest:
                    selected_export = latest
                    snapshot = latest.snapshot
                    context["selected_export_id"] = str(latest.pk)
                    active_download_url = reverse("export-download", args=[latest.pk])
                    context["preview_through"] = latest.snapshot.get("export_date")
                else:
                    through = min(max(timezone.localdate(), register.term_start), register.term_end)
                    snapshot = build_export_snapshot(request.user, register.pk, through=through, draft=True)
                    context["selected_export_id"] = ""
                    context["preview_through"] = through
            else:
                snapshot = build_export_snapshot(request.user, register.pk, through=through, draft=True)
                context["selected_export_id"] = ""
                context["preview_through"] = through
                latest = export_records.first()
                if latest:
                    active_download_url = reverse("export-download", args=[latest.pk])

        context["active_download_url"] = active_download_url
        context["preview_data"] = prepare_booklet_preview(snapshot)
    return render(request, "registers/workspace.html", context, status=status)


@login_required
@never_cache
@require_http_methods(["GET"])
def download_export(request, export_id):
    record = get_object_or_404(ExportRecord, pk=export_id, owner=request.user)
    try:
        downloads_dir = settings.BASE_DIR / "downloads"
        downloads_dir.mkdir(exist_ok=True)
        (downloads_dir / f"register-{record.pk}.docx").write_bytes(bytes(record.document))
    except Exception:
        pass
    response = HttpResponse(
        bytes(record.document),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    response["Content-Disposition"] = f'attachment; filename="register-{record.pk}.docx"'
    return response


@login_required
@never_cache
@require_http_methods(["GET"])
def export_preview(request, export_id):
    record = get_object_or_404(ExportRecord, pk=export_id, owner=request.user)
    return redirect(
        f"{reverse('register-workspace', args=[record.register.pk, 'preview'])}?export={record.pk}"
    )
