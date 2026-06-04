import { describe, expect, it } from "vitest";

import {
  CLASSROOM_CREDITS_MAX,
  CLASSROOM_SEAT_MAX,
  CLASSROOM_SEAT_MIN,
  buildClassroomPlanDraft,
  getClassroomLmsMetadata,
  type ClassroomLmsProvider,
} from "./classroom-plan";

describe("classroom-plan helper", () => {
  it("builds a deterministic manual cohort draft", () => {
    const result = buildClassroomPlanDraft({
      teacherEmail: "  professor@example.edu  ",
      courseName: "  Optimization 101  ",
      studentSeats: "25",
      sharedCreditsMonthlyRequest: "2000",
      lmsProvider: "manual_cohort",
    });

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.draft).toEqual({
      teacherEmail: "professor@example.edu",
      courseName: "Optimization 101",
      studentSeats: 25,
      sharedCreditsMonthlyRequest: 2000,
      lms: {
        provider: "manual_cohort",
        label: "Manual cohort",
        availability: "manual_v1",
        connected: false,
        integrationLabel: "v1 manual handling",
      },
      handlingMode: "v1_manual_cohort",
      boundaryCopy:
        "Local planning stub only: no teacher master account, students, credits, LMS connection, assignment, gradebook row or billing entry happens here.",
      sharedCreditsLabel: "manual request / planning estimate",
    });
  });

  it("marks all LMS providers as manual or planned and never connected", () => {
    const providers: ClassroomLmsProvider[] = [
      "manual_cohort",
      "canvas",
      "moodle",
      "yuketang",
      "xuetangx",
    ];

    expect(providers.map((provider) => getClassroomLmsMetadata(provider))).toEqual([
      {
        provider: "manual_cohort",
        label: "Manual cohort",
        availability: "manual_v1",
        connected: false,
        integrationLabel: "v1 manual handling",
      },
      {
        provider: "canvas",
        label: "Canvas",
        availability: "foundation_planned",
        connected: false,
        integrationLabel: "LTI 1.3 foundation / planned",
      },
      {
        provider: "moodle",
        label: "Moodle",
        availability: "foundation_planned",
        connected: false,
        integrationLabel: "LTI 1.3 foundation / planned",
      },
      {
        provider: "yuketang",
        label: "雨课堂",
        availability: "foundation_planned",
        connected: false,
        integrationLabel: "China LMS foundation / planned",
      },
      {
        provider: "xuetangx",
        label: "学堂在线",
        availability: "foundation_planned",
        connected: false,
        integrationLabel: "China LMS foundation / planned",
      },
    ]);
  });

  it("returns field-specific validation errors without throwing", () => {
    const result = buildClassroomPlanDraft({
      teacherEmail: "bad-email",
      courseName: "AI",
      studentSeats: "201",
      sharedCreditsMonthlyRequest: "2,000",
      lmsProvider: "blackboard",
    });

    expect(result).toEqual({
      ok: false,
      errors: {
        teacherEmail: "请输入有效教师联系人邮箱。",
        courseName: "课程名称需要 3-120 个字符。",
        studentSeats: `Classroom Plan cohort is capped at ${CLASSROOM_SEAT_MAX} students.`,
        sharedCreditsMonthlyRequest: "共享 Credits 申请必须是 0-2000000 的整数。",
        lmsProvider: "请选择有效 LMS provider。",
      },
    });
  });

  it("does not throw for non-string malformed inputs", () => {
    expect(() =>
      buildClassroomPlanDraft({
        teacherEmail: null,
        courseName: 42,
        studentSeats: Number.NaN,
        sharedCreditsMonthlyRequest: { amount: 1000 },
        lmsProvider: ["canvas"],
      }),
    ).not.toThrow();

    expect(
      buildClassroomPlanDraft({
        teacherEmail: null,
        courseName: 42,
        studentSeats: Number.NaN,
        sharedCreditsMonthlyRequest: { amount: 1000 },
        lmsProvider: ["canvas"],
      }),
    ).toEqual({
      ok: false,
      errors: {
        teacherEmail: "请输入有效教师联系人邮箱。",
        courseName: "课程名称需要 3-120 个字符。",
        studentSeats: "学生人数必须是 5-200 的整数。",
        sharedCreditsMonthlyRequest: "共享 Credits 申请必须是 0-2000000 的整数。",
        lmsProvider: "请选择有效 LMS provider。",
      },
    });
  });

  it("rejects seat and credits boundary values", () => {
    expect(
      buildClassroomPlanDraft({
        teacherEmail: "professor@example.edu",
        courseName: "Optimization 101",
        studentSeats: String(CLASSROOM_SEAT_MIN - 1),
        sharedCreditsMonthlyRequest: "0",
        lmsProvider: "manual_cohort",
      }),
    ).toEqual({
      ok: false,
      errors: {
        studentSeats: `Classroom Plan starts at ${CLASSROOM_SEAT_MIN} students.`,
      },
    });

    expect(
      buildClassroomPlanDraft({
        teacherEmail: "professor@example.edu",
        courseName: "Optimization 101",
        studentSeats: String(CLASSROOM_SEAT_MAX),
        sharedCreditsMonthlyRequest: String(CLASSROOM_CREDITS_MAX),
        lmsProvider: "canvas",
      }),
    ).toMatchObject({ ok: true });
  });

  it("rejects non-strict numeric strings", () => {
    const invalidValues = ["", " ", "10.0", "1e2", "1,000", "+10", "-1", "10 人", "1 0"];

    for (const value of invalidValues) {
      expect(
        buildClassroomPlanDraft({
          teacherEmail: "professor@example.edu",
          courseName: "Optimization 101",
          studentSeats: value,
          sharedCreditsMonthlyRequest: "1000",
          lmsProvider: "manual_cohort",
        }),
      ).toMatchObject({
        ok: false,
        errors: { studentSeats: "学生人数必须是 5-200 的整数。" },
      });

      expect(
        buildClassroomPlanDraft({
          teacherEmail: "professor@example.edu",
          courseName: "Optimization 101",
          studentSeats: "20",
          sharedCreditsMonthlyRequest: value,
          lmsProvider: "manual_cohort",
        }),
      ).toMatchObject({
        ok: false,
        errors: { sharedCreditsMonthlyRequest: "共享 Credits 申请必须是 0-2000000 的整数。" },
      });
    }
  });
});
