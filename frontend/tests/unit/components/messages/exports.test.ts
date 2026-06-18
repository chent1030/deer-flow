import { describe, expect, it } from "vitest";

import {
  MESSAGE_LIST_DEFAULT_PADDING_BOTTOM,
  MESSAGE_LIST_FOLLOWUPS_EXTRA_PADDING_BOTTOM,
} from "@/components/workspace/messages";

describe("workspace message exports", () => {
  it("keeps the legacy followups padding export compatible", () => {
    expect(MESSAGE_LIST_FOLLOWUPS_EXTRA_PADDING_BOTTOM).toBe(
      MESSAGE_LIST_DEFAULT_PADDING_BOTTOM,
    );
  });
});
