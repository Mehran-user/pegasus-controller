#!/usr/bin/env python3

import asyncio
import math
import os
import subprocess
import time
from dataclasses import dataclass, field

from evdev import InputDevice, ecodes, list_devices


# ============================================================
# CONFIGURATION
# ============================================================

PEGASUS_COMMAND = "/opt/pegasus-frontend/pegasus-fe"

# Home button timing
DOUBLE_TAP_TIME = 0.35
HOME_HOLD_TIME = 2.0

# ------------------------------------------------------------
# Mouse
# ------------------------------------------------------------

# Larger = less accidental movement from stick drift.
STICK_DEADZONE = 0.20

# Stick position at which actual mouse movement begins.
MOUSE_START_THRESHOLD = 0.025

# Maximum cursor speed in pixels/second.
MOUSE_MAX_SPEED = 1400.0

# How quickly the cursor accelerates.
MOUSE_ACCELERATION = 9.0

# How quickly the cursor stops when the stick is released.
MOUSE_DECELERATION = 15.0

# Extra smoothing.
MOUSE_SMOOTHING = 10.0

# Mouse update frequency.
MOUSE_HZ = 120.0

# ------------------------------------------------------------
# Scrolling
# ------------------------------------------------------------

SCROLL_DEADZONE = 0.20
SCROLL_SPEED = 12.0

# ------------------------------------------------------------
# Device discovery
# ------------------------------------------------------------

DEVICE_SCAN_INTERVAL = 0.5


# ============================================================
# SESSION DETECTION
# ============================================================

SESSION_TYPE = os.environ.get(
    "XDG_SESSION_TYPE",
    ""
).lower()

WAYLAND = (
    SESSION_TYPE == "wayland"
    or bool(os.environ.get("WAYLAND_DISPLAY"))
)

X11 = (
    bool(os.environ.get("DISPLAY"))
    and not WAYLAND
)


# ============================================================
# INPUT CODES
# ============================================================

HOME_CODES = {
    getattr(ecodes, "BTN_MODE", -1),
    getattr(ecodes, "KEY_HOME", -1),
    getattr(ecodes, "KEY_HOMEPAGE", -1),
}

A_CODES = {
    getattr(ecodes, "BTN_A", -1),
    getattr(ecodes, "BTN_SOUTH", -1),
}

X_CODES = {
    getattr(ecodes, "BTN_X", -1),
    getattr(ecodes, "BTN_WEST", -1),
}

Y_CODES = {
    getattr(ecodes, "BTN_Y", -1),
    getattr(ecodes, "BTN_NORTH", -1),
}


ABS_LX = getattr(ecodes, "ABS_X", None)
ABS_LY = getattr(ecodes, "ABS_Y", None)

ABS_RX = getattr(ecodes, "ABS_RX", None)
ABS_RY = getattr(ecodes, "ABS_RY", None)

ABS_LT = getattr(ecodes, "ABS_Z", None)
ABS_RT = getattr(ecodes, "ABS_RZ", None)


# ============================================================
# COMMAND HELPERS
# ============================================================

_COMMAND_CACHE = {}


def command_exists(command):
    if command in _COMMAND_CACHE:
        return _COMMAND_CACHE[command]

    try:
        result = subprocess.run(
            ["which", command],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        exists = result.returncode == 0

    except Exception:
        exists = False

    _COMMAND_CACHE[command] = exists

    return exists


def run_command(*args):
    try:
        return subprocess.run(
            list(args),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        )

    except Exception:
        return None


# ============================================================
# MATH
# ============================================================

def clamp(value, minimum, maximum):
    return max(
        minimum,
        min(maximum, value),
    )


def normalize_axis(value, minimum, maximum):
    if maximum <= minimum:
        return 0.0

    center = (minimum + maximum) / 2.0
    half_range = (maximum - minimum) / 2.0

    if half_range <= 0:
        return 0.0

    return clamp(
        (value - center) / half_range,
        -1.0,
        1.0,
    )


def apply_deadzone(
    value,
    deadzone=STICK_DEADZONE,
):
    magnitude = abs(value)

    if magnitude <= deadzone:
        return 0.0

    # Remap the area outside the deadzone from
    # deadzone..1 -> 0..1.
    magnitude = (
        magnitude - deadzone
    ) / (1.0 - deadzone)

    magnitude = clamp(
        magnitude,
        0.0,
        1.0,
    )

    sign = (
        1.0
        if value >= 0
        else -1.0
    )

    # Gentle center, strong edge.
    magnitude = magnitude ** 2.4

    return sign * magnitude


def approach(
    current,
    target,
    amount,
):
    if current < target:
        current += amount

        if current > target:
            current = target

    elif current > target:
        current -= amount

        if current < target:
            current = target

    return current


# ============================================================
# MOUSE BACKENDS
# ============================================================

def mouse_move(dx, dy):
    if abs(dx) < 0.01 and abs(dy) < 0.01:
        return

    # --------------------------------------------------------
    # Wayland / labwc
    # --------------------------------------------------------

    if WAYLAND and command_exists("wlrctl"):
        run_command(
            "wlrctl",
            "pointer",
            "move",
            str(int(round(dx))),
            str(int(round(dy))),
        )

        return

    # --------------------------------------------------------
    # X11 / Cinnamon
    # --------------------------------------------------------

    if X11 and command_exists("xdotool"):
        run_command(
            "xdotool",
            "mousemove_relative",
            "--",
            str(int(round(dx))),
            str(int(round(dy))),
        )

        return

    # --------------------------------------------------------
    # Wayland fallback
    # --------------------------------------------------------

    if command_exists("ydotool"):
        run_command(
            "ydotool",
            "mousemove",
            str(int(round(dx))),
            str(int(round(dy))),
        )


def mouse_click(button):
    """
    button:
        1 = left
        2 = middle
        3 = right
    """

    # Wayland
    if WAYLAND and command_exists("wlrctl"):
        run_command(
            "wlrctl",
            "pointer",
            "click",
            str(button),
        )

        return

    # X11
    if X11 and command_exists("xdotool"):
        run_command(
            "xdotool",
            "click",
            str(button),
        )

        return

    # ydotool fallback
    if command_exists("ydotool"):

        codes = {
            1: "0xC0",
            2: "0xC2",
            3: "0xC1",
        }

        code = codes.get(button)

        if code:
            run_command(
                "ydotool",
                "click",
                code,
            )


def mouse_scroll(amount):
    if abs(amount) < 0.05:
        return

    # labwc / Wayland
    if WAYLAND and command_exists("wlrctl"):
        run_command(
            "wlrctl",
            "pointer",
            "scroll",
            str(int(round(amount))),
        )

        return

    # X11 / Cinnamon
    if X11 and command_exists("xdotool"):

        button = (
            "4"
            if amount > 0
            else "5"
        )

        count = max(
            1,
            int(abs(amount)),
        )

        for _ in range(count):
            run_command(
                "xdotool",
                "click",
                button,
            )


# ============================================================
# KEYBOARD CONTROL
# ============================================================

def alt_f4():
    """
    Send a normal Alt+F4.

    This asks the focused application to close.
    It does NOT force-kill anything.
    """

    if X11 and command_exists("xdotool"):
        run_command(
            "xdotool",
            "key",
            "alt+F4",
        )

        return

    if command_exists("ydotool"):

        # Linux evdev keycodes:
        #
        # Left Alt = 56
        # F4       = 62

        run_command(
            "ydotool",
            "key",
            "56:1",
            "62:1",
            "62:0",
            "56:0",
        )


# ============================================================
# PEGASUS
# ============================================================

def pegasus_is_running():

    # Wayland / labwc
    if WAYLAND and command_exists("wlrctl"):

        result = run_command(
            "wlrctl",
            "toplevel",
            "find",
            "app_id:pegasus-fe",
        )

        return (
            result is not None
            and result.returncode == 0
        )

    # X11 / Cinnamon
    if X11 and command_exists("wmctrl"):

        result = run_command(
            "wmctrl",
            "-lx",
        )

        if result is None:
            return False

        text = result.stdout.lower()

        return (
            "pegasus-fe" in text
            or "pegasus frontend" in text
        )

    return False


def focus_pegasus():

    # Wayland / labwc
    if WAYLAND and command_exists("wlrctl"):

        result = run_command(
            "wlrctl",
            "toplevel",
            "focus",
            "app_id:pegasus-fe",
        )

        if (
            result is not None
            and result.returncode == 0
        ):
            return True

    # X11 / Cinnamon
    if X11 and command_exists("wmctrl"):

        # Try direct WM_CLASS.
        result = run_command(
            "wmctrl",
            "-xa",
            "pegasus-fe",
        )

        if (
            result is not None
            and result.returncode == 0
        ):
            return True

        # Search all windows.
        result = run_command(
            "wmctrl",
            "-lx",
        )

        if result is not None:

            for line in result.stdout.splitlines():

                if "pegasus-fe" not in line.lower():
                    continue

                parts = line.split()

                if not parts:
                    continue

                window_id = parts[0]

                run_command(
                    "wmctrl",
                    "-ia",
                    window_id,
                )

                return True

    return False


def launch_pegasus():

    print("Launching Pegasus...")

    try:

        subprocess.Popen(
            [PEGASUS_COMMAND],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        return True

    except Exception as error:

        print(
            f"Could not launch Pegasus: {error}"
        )

        return False


def open_or_focus_pegasus():

    if pegasus_is_running():

        print("Focusing Pegasus")

        focus_pegasus()

    else:

        launch_pegasus()


# ============================================================
# DEVICE STATE
# ============================================================

@dataclass
class DeviceState:

    device: InputDevice

    # --------------------------------------------------------
    # Home
    # --------------------------------------------------------

    home_down: bool = False

    home_pressed_at: float = 0.0

    home_hold_triggered: bool = False

    last_home_tap: float = 0.0

    # --------------------------------------------------------
    # Mouse mode
    # --------------------------------------------------------

    mouse_mode: bool = False

    # --------------------------------------------------------
    # Left stick
    # --------------------------------------------------------

    lx: float = 0.0
    ly: float = 0.0

    # --------------------------------------------------------
    # Right stick
    # --------------------------------------------------------

    rx: float = 0.0
    ry: float = 0.0

    # --------------------------------------------------------
    # Triggers
    # --------------------------------------------------------

    lt: float = 0.0
    rt: float = 0.0

    lt_down: bool = False
    rt_down: bool = False

    # --------------------------------------------------------
    # Smooth mouse velocity
    # --------------------------------------------------------

    mouse_velocity_x: float = 0.0
    mouse_velocity_y: float = 0.0

    # --------------------------------------------------------
    # Axis ranges
    # --------------------------------------------------------

    axis_ranges: dict = field(
        default_factory=dict
    )

    # --------------------------------------------------------
    # Lock
    # --------------------------------------------------------

    lock: asyncio.Lock = field(
        default_factory=asyncio.Lock
    )

    def load_axis_ranges(self):

        try:

            capabilities = self.device.capabilities(
                verbose=False
            )

            axes = capabilities.get(
                ecodes.EV_ABS,
                [],
            )

            for item in axes:

                if not isinstance(item, tuple):
                    continue

                code, info = item

                self.axis_ranges[code] = (
                    info.min,
                    info.max,
                )

        except Exception:
            pass


# ============================================================
# AXIS READING
# ============================================================

def get_axis_value(
    state,
    code,
    value,
):

    axis_range = state.axis_ranges.get(
        code
    )

    # Unknown trigger range.
    if axis_range is None:

        if code in (
            ABS_LT,
            ABS_RT,
        ):
            return clamp(
                value / 255.0,
                0.0,
                1.0,
            )

        return 0.0

    minimum, maximum = axis_range

    # Triggers are treated as 0..1.
    if code in (
        ABS_LT,
        ABS_RT,
    ):

        if maximum <= minimum:
            return 0.0

        return clamp(
            (
                value - minimum
            )
            / float(
                maximum - minimum
            ),
            0.0,
            1.0,
        )

    # Stick.
    return normalize_axis(
        value,
        minimum,
        maximum,
    )


# ============================================================
# SMOOTH MOUSE LOOP
# ============================================================

async def mouse_loop(state):

    interval = 1.0 / MOUSE_HZ

    last_time = time.monotonic()

    while True:

        await asyncio.sleep(interval)

        now = time.monotonic()

        dt = now - last_time
        last_time = now

        # Avoid huge movement after a pause.
        dt = clamp(
            dt,
            0.001,
            0.05,
        )

        async with state.lock:

            if not state.mouse_mode:

                # Smoothly stop any old velocity.
                state.mouse_velocity_x = 0.0
                state.mouse_velocity_y = 0.0

                continue

            # ------------------------------------------------
            # Left stick
            # ------------------------------------------------

            target_x = apply_deadzone(
                state.lx
            )

            target_y = apply_deadzone(
                state.ly
            )

            if (
                abs(target_x)
                < MOUSE_START_THRESHOLD
            ):
                target_x = 0.0

            if (
                abs(target_y)
                < MOUSE_START_THRESHOLD
            ):
                target_y = 0.0

            # ------------------------------------------------
            # Desired speed
            # ------------------------------------------------

            desired_x = (
                target_x
                * MOUSE_MAX_SPEED
            )

            desired_y = (
                target_y
                * MOUSE_MAX_SPEED
            )

            # ------------------------------------------------
            # Acceleration
            # ------------------------------------------------

            if (
                abs(desired_x)
                > abs(state.mouse_velocity_x)
            ):
                acceleration = (
                    MOUSE_ACCELERATION
                    * MOUSE_MAX_SPEED
                )

            else:
                acceleration = (
                    MOUSE_DECELERATION
                    * MOUSE_MAX_SPEED
                )

            state.mouse_velocity_x = approach(
                state.mouse_velocity_x,
                desired_x,
                acceleration * dt,
            )

            if (
                abs(desired_y)
                > abs(state.mouse_velocity_y)
            ):
                acceleration_y = (
                    MOUSE_ACCELERATION
                    * MOUSE_MAX_SPEED
                )

            else:
                acceleration_y = (
                    MOUSE_DECELERATION
                    * MOUSE_MAX_SPEED
                )

            state.mouse_velocity_y = approach(
                state.mouse_velocity_y,
                desired_y,
                acceleration_y * dt,
            )

            # ------------------------------------------------
            # Exponential smoothing
            # ------------------------------------------------

            smoothing = (
                1.0
                - math.exp(
                    -MOUSE_SMOOTHING * dt
                )
            )

            state.mouse_velocity_x += (
                desired_x
                - state.mouse_velocity_x
            ) * smoothing * 0.25

            state.mouse_velocity_y += (
                desired_y
                - state.mouse_velocity_y
            ) * smoothing * 0.25

            # ------------------------------------------------
            # Convert velocity to movement
            # ------------------------------------------------

            dx = (
                state.mouse_velocity_x
                * dt
            )

            dy = (
                state.mouse_velocity_y
                * dt
            )

            if (
                abs(dx) >= 0.01
                or abs(dy) >= 0.01
            ):
                mouse_move(
                    dx,
                    dy,
                )

            # ------------------------------------------------
            # Right stick scrolling
            # ------------------------------------------------

            scroll = apply_deadzone(
                state.ry,
                SCROLL_DEADZONE,
            )

            if abs(scroll) > 0:

                scroll_amount = (
                    -scroll
                    * SCROLL_SPEED
                    * dt
                    * 10.0
                )

                mouse_scroll(
                    scroll_amount
                )


# ============================================================
# HOME HOLD WATCHER
# ============================================================

async def home_hold_loop(state):

    while True:

        await asyncio.sleep(0.02)

        async with state.lock:

            if not state.home_down:
                continue

            if state.home_hold_triggered:
                continue

            elapsed = (
                time.monotonic()
                - state.home_pressed_at
            )

            if elapsed < HOME_HOLD_TIME:
                continue

            state.home_hold_triggered = True

            state.last_home_tap = 0.0

            print(
                f"[{state.device.name}] "
                "Home held -> Alt+F4"
            )

            alt_f4()


# ============================================================
# HOME BUTTON
# ============================================================

async def delayed_single_home(
    state,
    timestamp,
):

    await asyncio.sleep(
        DOUBLE_TAP_TIME
    )

    async with state.lock:

        # Another Home press occurred.
        if state.last_home_tap != timestamp:
            return

        # Don't launch Pegasus if the Home hold
        # already fired.
        if state.home_hold_triggered:
            return

        if state.mouse_mode:
            return

        state.mouse_mode = False
        state.mouse_velocity_x = 0.0
        state.mouse_velocity_y = 0.0

    print(
        f"[{state.device.name}] "
        "Home -> Pegasus"
    )

    open_or_focus_pegasus()


async def handle_home_press(state):

    now = time.monotonic()

    

    async with state.lock:

        # Double tap.
        if (
            state.last_home_tap != 0.0
            and (
                now
                - state.last_home_tap
                <= DOUBLE_TAP_TIME
            )
        ):

            state.last_home_tap = 0.0

            state.mouse_mode = (
                not state.mouse_mode
            )

            state.mouse_velocity_x = 0.0
            state.mouse_velocity_y = 0.0

            print(
                f"[{state.device.name}] "
                f"Mouse mode: "
                f"{'ON' if state.mouse_mode else 'OFF'}"
            )

            return

        # First tap.
        state.last_home_tap = now

    asyncio.create_task(
        delayed_single_home(
            state,
            now,
        )
    )


# ============================================================
# BUTTON / TRIGGER EVENTS
# ============================================================

async def handle_button(
    state,
    code,
    value,
):

    if value != 1:
        return

    async with state.lock:

        if not state.mouse_mode:
            return

    if code in A_CODES:

        mouse_click(1)

    elif code in X_CODES:

        mouse_click(2)

    elif code in Y_CODES:

        mouse_click(3)


async def handle_trigger(
    state,
    code,
    value,
):

    async with state.lock:

        if not state.mouse_mode:
            return

        if code == ABS_RT:

            # Press threshold.
            pressed = value >= 0.75

            if pressed and not state.rt_down:

                state.rt_down = True

                mouse_click(1)

            elif not pressed:

                state.rt_down = False

        elif code == ABS_LT:

            pressed = value >= 0.75

            if pressed and not state.lt_down:

                state.lt_down = True

                mouse_click(3)

            elif not pressed:

                state.lt_down = False


# ============================================================
# DEVICE EVENT LOOP
# ============================================================

async def device_loop(state):

    device = state.device

    print(
        f"Listening: "
        f"{device.path} -> "
        f"{device.name}"
    )

    try:

        async for event in (
            device.async_read_loop()
        ):

            # ------------------------------------------------
            # Buttons
            # ------------------------------------------------

            if event.type == ecodes.EV_KEY:

                code = event.code
                value = event.value

                if code in HOME_CODES:

                    if value == 1:

                        async with state.lock:

                            if state.home_down:
                                continue

                            state.home_down = True
                            state.home_pressed_at = (
                                time.monotonic()
                            )
                            state.home_hold_triggered = (
                                False
                            )

                        await handle_home_press(
                            state
                        )

                    elif value == 0:

                        async with state.lock:

                            state.home_down = False

                    continue

                await handle_button(
                    state,
                    code,
                    value,
                )

            # ------------------------------------------------
            # Analog axes
            # ------------------------------------------------

            elif event.type == ecodes.EV_ABS:

                code = event.code
                value = event.value

                async with state.lock:

                    if code == ABS_LX:

                        state.lx = get_axis_value(
                            state,
                            code,
                            value,
                        )

                    elif code == ABS_LY:

                        state.ly = get_axis_value(
                            state,
                            code,
                            value,
                        )

                    elif code == ABS_RX:

                        state.rx = get_axis_value(
                            state,
                            code,
                            value,
                        )

                    elif code == ABS_RY:

                        state.ry = get_axis_value(
                            state,
                            code,
                            value,
                        )

                    elif code == ABS_LT:

                        state.lt = get_axis_value(
                            state,
                            code,
                            value,
                        )

                    elif code == ABS_RT:

                        state.rt = get_axis_value(
                            state,
                            code,
                            value,
                        )

                if code in (
                    ABS_LT,
                    ABS_RT,
                ):

                    await handle_trigger(
                        state,
                        code,
                        state.lt
                        if code == ABS_LT
                        else state.rt,
                    )

    except OSError:

        print(
            f"Disconnected: "
            f"{device.path} "
            f"({device.name})"
        )

    except Exception as error:

        print(
            f"Error reading "
            f"{device.path}: {error}"
        )

    finally:

        try:
            device.close()
        except Exception:
            pass


# ============================================================
# DISCOVERY
# ============================================================

def discover_devices():

    """
    Deliberately does NOT detect controllers.

    Every readable evdev device is opened.

    Sunshine can therefore create a controller after
    this program has already started.
    """

    devices = {}

    for path in list_devices():

        try:

            device = InputDevice(path)

            # Check that it is readable.
            device.capabilities()

            devices[path] = device

        except (
            PermissionError,
            OSError,
        ):

            continue

        except Exception:

            continue

    return devices


# ============================================================
# MAIN
# ============================================================

async def main():

    print()
    print("============================================")
    print(" Gamepad Desktop Control")
    print("============================================")
    print()
    print(
        "Controller detection: DISABLED"
    )
    print(
        "Listening to every readable evdev device."
    )
    print()
    print("HOME")
    print(
        "  Single press -> Launch/focus Pegasus"
    )
    print(
        "  Double press -> Toggle mouse mode"
    )
    print(
        "  Hold 2 sec   -> Alt+F4"
    )
    print()
    print("MOUSE MODE")
    print(
        "  Left stick  -> Smooth mouse"
    )
    print(
        "  Right stick -> Scroll"
    )
    print(
        "  RT -> Left click"
    )
    print(
        "  LT -> Right click"
    )
    print(
        "  A  -> Left click"
    )
    print(
        "  X  -> Middle click"
    )
    print(
        "  Y  -> Right click"
    )
    print()
    print(
        f"Session: "
        f"{'Wayland' if WAYLAND else 'X11' if X11 else 'unknown'}"
    )
    print()
    print("Waiting for input devices...")
    print()

    tasks = {}
    states = {}

    while True:

        devices = discover_devices()

        # ----------------------------------------------------
        # New devices
        # ----------------------------------------------------

        for path, device in devices.items():

            if path in tasks:

                try:
                    device.close()
                except Exception:
                    pass

                continue

            state = DeviceState(device)

            state.load_axis_ranges()

            states[path] = state

            # Input reader.
            reader_task = asyncio.create_task(
                device_loop(state)
            )

            # Smooth mouse updater.
            mouse_task = asyncio.create_task(
                mouse_loop(state)
            )

            # Home hold watcher.
            hold_task = asyncio.create_task(
                home_hold_loop(state)
            )

            tasks[path] = (
                reader_task,
                mouse_task,
                hold_task,
            )

        # ----------------------------------------------------
        # Finished / disconnected devices
        # ----------------------------------------------------

        for path in list(tasks):

            reader_task, mouse_task, hold_task = (
                tasks[path]
            )

            if reader_task.done():

                try:
                    reader_task.result()
                except Exception:
                    pass

                mouse_task.cancel()
                hold_task.cancel()

                tasks.pop(path, None)
                states.pop(path, None)

        await asyncio.sleep(
            DEVICE_SCAN_INTERVAL
        )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:

        print()
        print("Exiting.")