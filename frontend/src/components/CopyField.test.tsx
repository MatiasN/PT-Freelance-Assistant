import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { CopyField } from "./CopyField";

const field = { portal_label: "Regime de IVA", value: "Artigo 6.º", hint: "M99" };

it("copies the value to the clipboard", async () => {
  const user = userEvent.setup();
  render(<CopyField field={field} />);

  await user.click(screen.getByRole("button", { name: "Copy Regime de IVA" }));

  expect(await navigator.clipboard.readText()).toBe("Artigo 6.º");
  expect(screen.getByRole("button")).toHaveTextContent("Copied");
});

it("tells the user to copy manually when the clipboard is unavailable", async () => {
  const user = userEvent.setup();
  render(<CopyField field={field} />);
  vi.spyOn(navigator.clipboard, "writeText").mockRejectedValueOnce(new Error("insecure"));

  await user.click(screen.getByRole("button", { name: "Copy Regime de IVA" }));

  expect(screen.getByRole("button")).toHaveTextContent("Select & copy manually");
});
