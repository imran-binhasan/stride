import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AuthPage } from "./AuthPage";

describe("AuthPage", () => {
  it("renders the sign-in form without prefilled credentials", () => {
    render(<AuthPage onSuccess={() => {}} />);
    expect(screen.getByText("STRIDE")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Sign In to Workspace/i })).toBeInTheDocument();

    const email = screen.getByPlaceholderText("name@company.com") as HTMLInputElement;
    expect(email.value).toBe(""); // no hardcoded demo credentials shipped
  });
});
