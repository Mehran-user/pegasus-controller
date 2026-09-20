# 🎮 Linux Controller Desktop Control

A lightweight Python script that lets game controllers act as a desktop controller on Linux.

It is designed to work with **labwc**, **Cinnamon**, and other Linux desktop environments. Instead of trying to identify controllers by name, it listens to **all readable evdev input devices** and reacts to devices that provide the expected controller-style buttons/axes.

## Features

* 🎮 Supports multiple controllers simultaneously
* 🔌 Waits for controllers instead of exiting when none are connected
* 🖱️ Controller-powered mouse mode
* 🎯 Smooth analog-stick mouse movement
* 🖱️ Right stick scrolling
* 🖱️ Analog triggers as mouse buttons
* 🕹️ Face buttons as mouse buttons
* 🏠 Home/Guide button controls
* 🚀 Launches or focuses Pegasus
* ❌ Hold Home to send normal `Alt+F4`
* 🖥️ Supports Wayland/labwc
* 🖥️ Supports X11/Cinnamon
* 🔄 Continuously detects newly connected input devices

---

## Requirements

### Python

Python 3.9+ is recommended.

Install `evdev`:

```bash
python3 -m pip install evdev
```

On some distributions you may need:

```bash
sudo apt install python3-evdev
```

### Desktop control tools

Depending on your desktop/session, the script can use:

#### Wayland / labwc

* `wlrctl`
* or `ydotool` as a fallback

#### X11 / Cinnamon

* `xdotool`
* optionally `wmctrl` for window focusing

Install the tools appropriate for your system.

---

## Running

Save the script somewhere convenient, for example:

```text
~/controller-desktop.py
```

Then run:

```bash
python3 ~/controller-desktop.py
```

The script will keep running even if no controller is connected.

Connect a controller later and it will automatically scan for it.

---

# Controls

## Home / Guide

The Home button is used for desktop control.

### Home press

Toggles controller mouse mode.

When mouse mode is turned off, mouse velocity is immediately reset so the cursor does not continue moving.

### Hold Home

Holding Home for approximately **2 seconds** sends:

```text
Alt + F4
```

This closes the currently focused application normally rather than force-killing it.

---

# Mouse Mode

When mouse mode is enabled:

| Controller input | Desktop action |
| ---------------- | -------------- |
| Left stick       | Move mouse     |
| Right stick      | Scroll         |
| RT               | Left click     |
| LT               | Right click    |
| A / South        | Left click     |
| Y / North        | Right click    |
| X / West         | Middle click   |

The analog mouse uses:

* A deadzone to prevent stick drift
* Acceleration
* Deceleration
* Smoothing
* A dedicated high-frequency update loop

This makes the cursor movement feel less twitchy than directly converting every joystick event into mouse movement.

---

# Pegasus

The Home/Pegasus behavior can be connected to a Pegasus installation.

The script can:

1. Start Pegasus if it isn't running.
2. Focus the existing Pegasus window if it is already running.

The exact launch command can be changed in the `open_or_focus_pegasus()` function.

---

# Supported Sessions

The script detects the current graphical session using environment variables such as:

```text
XDG_SESSION_TYPE
WAYLAND_DISPLAY
DISPLAY
```

### Wayland

For labwc/Wayland, the script attempts to use Wayland-compatible mouse-control tools.

### X11

For X11 desktops such as Cinnamon running under X11, it can use tools such as:

```text
xdotool
wmctrl
```

---

# Why evdev?

The script intentionally does **not** require a device to identify itself as a traditional game controller.

Instead, it opens readable Linux evdev input devices and listens for relevant events.

This is useful for:

* Normal USB controllers
* Bluetooth controllers
* Virtual controllers
* Sunshine/Moonlight virtual input devices
* Unusual controller implementations

It also means that keyboards and other input devices can technically be opened if they are readable. The script only reacts to the button/axis events it is interested in.

---

# Multiple Controllers

Multiple devices can be active at the same time.

Each device gets its own state, including:

* Home button state
* Mouse mode
* Stick positions
* Trigger states
* Mouse velocity

This allows multiple controllers to operate independently.

---

# Configuration

The mouse behavior can be adjusted near the top of the script.

For example:

```python
STICK_DEADZONE = 0.20
MOUSE_START_THRESHOLD = 0.025
MOUSE_MAX_SPEED = 1400.0
MOUSE_ACCELERATION = 9.0
MOUSE_DECELERATION = 15.0
MOUSE_SMOOTHING = 10.0
MOUSE_HZ = 120.0
```

### `STICK_DEADZONE`

How far the stick must move before it starts controlling the mouse.

Increase it if the cursor moves when the stick is supposed to be centered.

### `MOUSE_MAX_SPEED`

Maximum cursor speed.

Increase it for faster movement or decrease it for more precise control.

### `MOUSE_ACCELERATION`

How quickly the cursor reaches its target speed.

### `MOUSE_DECELERATION`

How quickly the cursor stops when the stick is released.

### `MOUSE_SMOOTHING`

Controls how smoothly the cursor approaches its target velocity.

### `MOUSE_HZ`

How frequently the mouse movement loop runs.

The default is:

```text
120 Hz
```

---

# Troubleshooting

## No controller is detected

The script intentionally doesn't require controller identification.

Check that the device exists under:

```bash
ls /dev/input/event*
```

You can inspect devices with:

```bash
cat /proc/bus/input/devices
```

You can also run the script from a terminal and watch its device messages.

---

## Permission denied

Your user may not have permission to read `/dev/input/event*`.

On many Linux distributions, input devices belong to the `input` group.

Check:

```bash
ls -l /dev/input/event*
```

If necessary, configure your distribution's input-device permissions appropriately.

---

## Mouse movement does not work on Wayland

Make sure the required Wayland mouse-control utility is installed and usable by your user.

Depending on the configuration, you may need `wlrctl` or `ydotool`.

---

## Mouse movement feels too fast

Lower:

```python
MOUSE_MAX_SPEED
```

For example:

```python
MOUSE_MAX_SPEED = 900.0
```

## Mouse movement feels too slow

Increase it:

```python
MOUSE_MAX_SPEED = 1800.0
```

You can also adjust acceleration.

---

## Stick drift

Increase:

```python
STICK_DEADZONE
```

For example:

```python
STICK_DEADZONE = 0.25
```

---

# Running Automatically

If you want the script to start automatically when you log into your desktop, it can be launched using your desktop/session's autostart mechanism.

For labwc, this can be added to the appropriate labwc autostart configuration.

For Cinnamon, you can add the script through:

**System Settings → Startup Applications**

A typical command is:

```bash
python3 /path/to/controller-desktop.py
```

---

# License

Use, modify, and adapt the script for your own setup.
