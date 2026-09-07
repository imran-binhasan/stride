import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CalendarPage } from "./CalendarPage";
import { api } from "../services/api";
import { Project } from "../types";

const project = { id: "p1", name: "Proj", statuses: [] } as unknown as Project;

describe("CalendarPage", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("fetches the calendar on mount and refetches when the month changes", async () => {
    const spy = vi
      .spyOn(api, "getCalendar")
      .mockResolvedValue({ project_id: "p1", events: [] } as never);

    render(<CalendarPage project={project} />);

    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1));
    const [, monthOnMount] = spy.mock.calls[0];

    // The two nav buttons are prev / next; click prev to change the month.
    const prevButton = screen.getAllByRole("button")[0];
    fireEvent.click(prevButton);

    await waitFor(() => expect(spy).toHaveBeenCalledTimes(2));
    const [, monthAfterPrev] = spy.mock.calls[1];
    expect(monthAfterPrev).not.toBe(monthOnMount); // it actually refetched for a new month
  });
});
