export const CLASSROOM_SEAT_MIN = 5;
export const CLASSROOM_SEAT_MAX = 200;
export const CLASSROOM_CREDITS_MAX = 2_000_000;

export type ClassroomLmsProvider = "manual_cohort" | "canvas" | "moodle" | "yuketang" | "xuetangx";

export type ClassroomLmsAvailability = "manual_v1" | "foundation_planned";

export interface ClassroomLmsMetadata {
  provider: ClassroomLmsProvider;
  label: string;
  availability: ClassroomLmsAvailability;
  connected: false;
  integrationLabel: string;
}

export interface ClassroomPlanDraftInput {
  teacherEmail: unknown;
  courseName: unknown;
  studentSeats: unknown;
  sharedCreditsMonthlyRequest: unknown;
  lmsProvider: unknown;
}

export interface ClassroomPlanDraft {
  teacherEmail: string;
  courseName: string;
  studentSeats: number;
  sharedCreditsMonthlyRequest: number;
  lms: ClassroomLmsMetadata;
  handlingMode: "v1_manual_cohort";
  boundaryCopy: string;
  sharedCreditsLabel: "manual request / planning estimate";
}

export interface ClassroomPlanValidationErrors {
  teacherEmail?: string;
  courseName?: string;
  studentSeats?: string;
  sharedCreditsMonthlyRequest?: string;
  lmsProvider?: string;
}

export type ClassroomPlanDraftResult =
  | { ok: true; draft: ClassroomPlanDraft }
  | { ok: false; errors: ClassroomPlanValidationErrors };

const lmsMetadata: Record<ClassroomLmsProvider, ClassroomLmsMetadata> = {
  manual_cohort: {
    provider: "manual_cohort",
    label: "Manual cohort",
    availability: "manual_v1",
    connected: false,
    integrationLabel: "v1 manual handling",
  },
  canvas: {
    provider: "canvas",
    label: "Canvas",
    availability: "foundation_planned",
    connected: false,
    integrationLabel: "LTI 1.3 foundation / planned",
  },
  moodle: {
    provider: "moodle",
    label: "Moodle",
    availability: "foundation_planned",
    connected: false,
    integrationLabel: "LTI 1.3 foundation / planned",
  },
  yuketang: {
    provider: "yuketang",
    label: "雨课堂",
    availability: "foundation_planned",
    connected: false,
    integrationLabel: "China LMS foundation / planned",
  },
  xuetangx: {
    provider: "xuetangx",
    label: "学堂在线",
    availability: "foundation_planned",
    connected: false,
    integrationLabel: "China LMS foundation / planned",
  },
};

const providerKeys = new Set<string>(Object.keys(lmsMetadata));

function normalizeText(value: unknown): string {
  if (typeof value !== "string") return "";
  return value.trim().replace(/\s+/g, " ");
}

function parseStrictInteger(value: unknown): number | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (!/^[0-9]+$/.test(trimmed)) return null;
  const parsed = Number(trimmed);
  if (!Number.isSafeInteger(parsed)) return null;
  return parsed;
}

function isClassroomLmsProvider(value: string): value is ClassroomLmsProvider {
  return providerKeys.has(value);
}

export function getClassroomLmsMetadata(provider: ClassroomLmsProvider): ClassroomLmsMetadata {
  return lmsMetadata[provider];
}

export function buildClassroomPlanDraft(
  input: ClassroomPlanDraftInput,
): ClassroomPlanDraftResult {
  const teacherEmail = normalizeText(input.teacherEmail);
  const courseName = normalizeText(input.courseName);
  const studentSeats = parseStrictInteger(input.studentSeats);
  const sharedCreditsMonthlyRequest = parseStrictInteger(input.sharedCreditsMonthlyRequest);
  const lmsProvider = typeof input.lmsProvider === "string" ? input.lmsProvider.trim() : "";
  const errors: ClassroomPlanValidationErrors = {};

  if (!teacherEmail || teacherEmail.length > 254 || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(teacherEmail)) {
    errors.teacherEmail = "请输入有效教师联系人邮箱。";
  }

  if (courseName.length < 3 || courseName.length > 120) {
    errors.courseName = "课程名称需要 3-120 个字符。";
  }

  if (studentSeats === null) {
    errors.studentSeats = "学生人数必须是 5-200 的整数。";
  } else if (studentSeats < CLASSROOM_SEAT_MIN) {
    errors.studentSeats = `Classroom Plan starts at ${CLASSROOM_SEAT_MIN} students.`;
  } else if (studentSeats > CLASSROOM_SEAT_MAX) {
    errors.studentSeats = `Classroom Plan cohort is capped at ${CLASSROOM_SEAT_MAX} students.`;
  }

  if (
    sharedCreditsMonthlyRequest === null ||
    sharedCreditsMonthlyRequest < 0 ||
    sharedCreditsMonthlyRequest > CLASSROOM_CREDITS_MAX
  ) {
    errors.sharedCreditsMonthlyRequest = "共享 Credits 申请必须是 0-2000000 的整数。";
  }

  const validLmsProvider = isClassroomLmsProvider(lmsProvider) ? lmsProvider : null;
  if (!validLmsProvider) {
    errors.lmsProvider = "请选择有效 LMS provider。";
  }

  if (Object.keys(errors).length > 0) {
    return { ok: false, errors };
  }

  if (studentSeats === null || sharedCreditsMonthlyRequest === null || !validLmsProvider) {
    return { ok: false, errors };
  }

  return {
    ok: true,
    draft: {
      teacherEmail,
      courseName,
      studentSeats,
      sharedCreditsMonthlyRequest,
      lms: getClassroomLmsMetadata(validLmsProvider),
      handlingMode: "v1_manual_cohort",
      boundaryCopy:
        "Local planning stub only: no teacher master account, students, credits, LMS connection, assignment, gradebook row or billing entry happens here.",
      sharedCreditsLabel: "manual request / planning estimate",
    },
  };
}
