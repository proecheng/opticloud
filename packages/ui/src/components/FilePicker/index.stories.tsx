import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "@storybook/test";

import { FilePicker } from "./index";

const meta = { title: "Tier 1/FilePicker", component: FilePicker, parameters: { layout: "centered" } } satisfies Meta<typeof FilePicker>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = { args: { ariaLabel: "file_picker.csv_excel", onFile: fn() } };
export const ChatN8: Story = { args: { ariaLabel: "file_picker.chat_n8", accept: ".csv,.xlsx,.json", onFile: fn(), label: "上传 CSV / Excel / JSON" } };
