import userEvent from "@testing-library/user-event";

/**
 * user-event with `delay: null`: the default `delay: 0` awaits a setTimeout(0) between every
 * keystroke, which costs ~25 ms per key under jsdom; without it the same events are dispatched
 * in ~7 ms per key.
 */
export function setupUser() {
  return userEvent.setup({ delay: null });
}
