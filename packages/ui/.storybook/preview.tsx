/** Storybook preview — global decorators / parameters. */

import type { Preview } from "@storybook/react";
import "../src/tokens.css";

const preview: Preview = {
  parameters: {
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
    // UX-DR9 P74 Chromatic visual regression
    chromatic: {
      pauseAnimationAtEnd: true,
      delay: 100,
    },
    // a11y addon: violation = error
    a11y: {
      element: "#storybook-root",
      manual: false,
    },
    backgrounds: {
      default: "light",
      values: [
        { name: "light", value: "#FFFFFF" },
        { name: "dark", value: "#0D1117" }, // GitHub-aligned (UX Spec Step 8)
      ],
    },
  },
  globalTypes: {
    theme: {
      description: "Light / Dark mode",
      defaultValue: "light",
      toolbar: {
        title: "Theme",
        icon: "circlehollow",
        items: ["light", "dark"],
      },
    },
  },
  decorators: [
    (Story, context) => {
      const theme = (context.globals.theme as string) ?? "light";
      return (
        <div
          className={theme === "dark" ? "dark" : ""}
          style={{
            background: theme === "dark" ? "#0D1117" : "#FFFFFF",
            color: theme === "dark" ? "#E6EDF3" : "#111827",
            minHeight: "100vh",
            padding: "16px",
          }}
        >
          <Story />
        </div>
      );
    },
  ],
};

export default preview;
