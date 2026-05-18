import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "@storybook/test";

import { ExcelDropZone } from "./index";

const meta = { title: "Tier 1/ExcelDropZone", component: ExcelDropZone, parameters: { layout: "centered" } } satisfies Meta<typeof ExcelDropZone>;
export default meta;
type Story = StoryObj<typeof meta>;

export const ZhangLao老张Surface: Story = { args: { onFile: fn() } };
