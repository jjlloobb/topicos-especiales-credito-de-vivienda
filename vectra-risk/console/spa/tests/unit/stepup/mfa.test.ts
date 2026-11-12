// BR-U10-06: «MFA reciente» = `mfa` y `auth_time` de hace <= 900 s.
import { describe, expect, it } from "vitest";
import { recentMfa } from "../../../src/stepup/mfa";

const NOW = Date.parse("2026-11-12T15:00:00Z");
const ago = (seconds: number) => new Date(NOW - seconds * 1000).toISOString();

describe("recentMfa", () => {
  it.each([
    [true, 0, true],
    [true, 900, true],
    [true, 901, false],
    [false, 0, false],
    [false, 1000, false],
  ])("mfa=%s, hace %i s -> %s", (mfa, seconds, expected) => {
    expect(recentMfa({ mfa, auth_time: ago(seconds) }, NOW)).toBe(expected);
  });
});
