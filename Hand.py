import cv2
import mediapipe as mp
import pyautogui
import numpy as np
import time
import threading
import math
import os
import tkinter as tk
from tkinter import ttk, messagebox
import pygame
import speech_recognition as sr
import json

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
pygame.mixer.init()

CONFIG_FILE = "gesture_mappings.json"
ACTIONS = [
    "move_cursor", "left_click", "right_click", "scroll_up", "scroll_down",
    "swipe_left", "swipe_right", "swipe_up", "swipe_down",
    "app_switch", "volume_up", "volume_down", "zoom_in", "zoom_out"
]

exit_requested = False  # Flag to exit main loop safely

# Voice command listener runs in background to set exit_requested when "exit" is spoken
def listen_for_exit_command():
    global exit_requested
    recognizer = sr.Recognizer()
    mic = sr.Microphone()
    with mic as source:
        recognizer.adjust_for_ambient_noise(source)
    while not exit_requested:
        try:
            with mic as source:
                audio = recognizer.listen(source, timeout=5)
            command = recognizer.recognize_google(audio).lower()
            print(f"[Voice Command] Detected: {command}")
            if any(word in command for word in ("exit", "quit", "close")):
                print("[Voice Command] Exit requested.")
                exit_requested = True
        except sr.WaitTimeoutError:
            continue
        except sr.UnknownValueError:
            continue
        except sr.RequestError as e:
            print("Speech Recognition Error:", e)
            continue

def play_sound(file):
    def _play():
        try:
            pygame.mixer.music.load(file)
            pygame.mixer.music.play()
        except Exception as e:
            print("Audio Error:", e)
    threading.Thread(target=_play, daemon=True).start()

def fingers_up(landmarks):
    tips = [8, 12, 16, 20]
    fingers = [1 if landmarks[4].x < landmarks[3].x else 0]  # Thumb (right hand)
    fingers += [1 if landmarks[tip].y < landmarks[tip - 2].y else 0 for tip in tips]
    return fingers

def load_mappings():
    try:
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
            return data.get("mappings", [])
    except FileNotFoundError:
        return []

def save_mappings(mappings):
    with open(CONFIG_FILE, 'w') as f:
        json.dump({"mappings": mappings}, f, indent=2)

# GUI to add/edit gesture mappings
class GestureMappingApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gesture to Action Mapper")
        self.mappings = load_mappings()

        self.tree = ttk.Treeview(self, columns=("Gesture", "Action"), show="headings")
        self.tree.heading("Gesture", text="Gesture (Thumb-Index-Middle-Ring-Pinky)")
        self.tree.heading("Action", text="Action")
        self.tree.pack(fill=tk.BOTH, expand=True)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="Add", command=self.add_mapping).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Edit", command=self.edit_mapping).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Delete", command=self.delete_mapping).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Start Gesture Control", command=self.destroy).pack(side=tk.RIGHT, padx=5)

        self.refresh_tree()

    def refresh_tree(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for m in self.mappings:
            gesture_str = "".join(str(b) for b in m["gesture"])
            self.tree.insert("", tk.END, values=(gesture_str, m["action"]))

    def add_mapping(self):
        MappingEditor(self, self.mappings, self.refresh_tree).grab_set()

    def edit_mapping(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Select item", "Please select a mapping to edit.")
            return
        idx = self.tree.index(selected[0])
        MappingEditor(self, self.mappings, self.refresh_tree, idx).grab_set()

    def delete_mapping(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Select item", "Please select a mapping to delete.")
            return
        idx = self.tree.index(selected[0])
        del self.mappings[idx]
        save_mappings(self.mappings)
        self.refresh_tree()

class MappingEditor(tk.Toplevel):
    def __init__(self, parent, mappings, refresh_callback, edit_idx=None):
        super().__init__(parent)
        self.title("Edit Mapping" if edit_idx is not None else "Add Mapping")
        self.mappings = mappings
        self.refresh_callback = refresh_callback
        self.edit_idx = edit_idx

        self.vars = [tk.IntVar() for _ in range(5)]
        fingers = ["Thumb", "Index", "Middle", "Ring", "Pinky"]
        for i, f in enumerate(fingers):
            cb = ttk.Checkbutton(self, text=f, variable=self.vars[i])
            cb.grid(row=0, column=i, padx=5, pady=5)

        ttk.Label(self, text="Action:").grid(row=1, column=0, pady=10, sticky=tk.W)
        self.action_var = tk.StringVar()
        self.action_combo = ttk.Combobox(self, values=ACTIONS, textvariable=self.action_var, state="readonly")
        self.action_combo.grid(row=1, column=1, columnspan=4, sticky=tk.W + tk.E, padx=5)

        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=2, column=0, columnspan=5, pady=10)
        ttk.Button(btn_frame, text="Save", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=5)

        if edit_idx is not None:
            self.load_existing()

    def load_existing(self):
        mapping = self.mappings[self.edit_idx]
        for i, val in enumerate(mapping["gesture"]):
            self.vars[i].set(val)
        self.action_var.set(mapping["action"])

    def save(self):
        gesture = [var.get() for var in self.vars]
        action = self.action_var.get()
        if not any(gesture):
            messagebox.showerror("Invalid Gesture", "At least one finger must be selected.")
            return
        if not action:
            messagebox.showerror("Invalid Action", "Please select an action.")
            return

        new_mapping = {"gesture": gesture, "action": action}
        if self.edit_idx is not None:
            self.mappings[self.edit_idx] = new_mapping
        else:
            self.mappings.append(new_mapping)

        save_mappings(self.mappings)
        self.refresh_callback()
        self.destroy()

class SettingsUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gesture Control Settings")
        self.ui_scroll_speed = tk.IntVar(value=40)
        self.ui_action_delay = tk.DoubleVar(value=0.7)

        ttk.Label(self, text="Scroll Speed:").pack()
        ttk.Scale(self, from_=10, to=100, variable=self.ui_scroll_speed, orient=tk.HORIZONTAL).pack()
        ttk.Label(self, text="Action Delay (sec):").pack()
        tk.Scale(self, from_=0.1, to=2.0, resolution=0.1, variable=self.ui_action_delay, orient=tk.HORIZONTAL).pack()
        ttk.Button(self, text="Next: Map Gestures", command=self.destroy).pack()

def handle_action(action, current_time, last_action_time, last_scroll_time, ui_scroll_speed):
    delay = 0.7
    if action == "move_cursor":
        pass
    elif action == "left_click" and current_time - last_action_time > delay:
        pyautogui.click()
        play_sound("click.mp3")
        last_action_time = current_time
    elif action == "right_click" and current_time - last_action_time > delay:
        pyautogui.rightClick()
        play_sound("right_click.mp3")
        last_action_time = current_time
    elif action == "scroll_up" and current_time - last_scroll_time > 0.5:
        pyautogui.scroll(ui_scroll_speed)
        play_sound("scroll_up.mp3")
        last_scroll_time = current_time
    elif action == "scroll_down" and current_time - last_scroll_time > 0.5:
        pyautogui.scroll(-ui_scroll_speed)
        play_sound("scroll_down.mp3")
        last_scroll_time = current_time
    elif action == "swipe_left" and current_time - last_action_time > delay:
        pyautogui.press('left')
        play_sound("swipe_left.mp3")
        last_action_time = current_time
    elif action == "swipe_right" and current_time - last_action_time > delay:
        pyautogui.press('right')
        play_sound("swipe_right.mp3")
        last_action_time = current_time
    elif action == "swipe_up" and current_time - last_action_time > delay:
        pyautogui.press('up')
        play_sound("swipe_up.mp3")
        last_action_time = current_time
    elif action == "swipe_down" and current_time - last_action_time > delay:
        pyautogui.press('down')
        play_sound("swipe_down.mp3")
        last_action_time = current_time
    elif action == "app_switch" and current_time - last_action_time > delay:
        pyautogui.hotkey('alt', 'tab')
        play_sound("app_switch.mp3")
        last_action_time = current_time
    elif action == "volume_up" and current_time - last_action_time > delay:
        pyautogui.press('volumeup')
        play_sound("volume_up.mp3")
        last_action_time = current_time
    elif action == "volume_down" and current_time - last_action_time > delay:
        pyautogui.press('volumedown')
        play_sound("volume_down.mp3")
        last_action_time = current_time
    elif action == "zoom_in" and current_time - last_action_time > delay:
        pyautogui.hotkey('ctrl', '+')
        play_sound("zoom_in.mp3")
        last_action_time = current_time
    elif action == "zoom_out" and current_time - last_action_time > delay:
        pyautogui.hotkey('ctrl', '-')
        play_sound("zoom_out.mp3")
        last_action_time = current_time
    return last_action_time, last_scroll_time

def main():
    global exit_requested
    # Show settings UI
    settings_ui = SettingsUI()
    settings_ui.mainloop()
    scroll_speed = settings_ui.ui_scroll_speed.get()
    action_delay = settings_ui.ui_action_delay.get()

    # Show gesture-action mapping UI
    mapping_ui = GestureMappingApp()
    mapping_ui.mainloop()

    mappings = load_mappings()
    if not mappings:
        print("No gesture mappings found. Exiting.")
        return

    # Start voice recognition thread
    voice_thread = threading.Thread(target=listen_for_exit_command, daemon=True)
    voice_thread.start()

    # Mediapipe and OpenCV setup
    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(min_detection_confidence=0.7, min_tracking_confidence=0.7)
    mp_draw = mp.solutions.drawing_utils

    cap = cv2.VideoCapture(0)
    screen_w, screen_h = pyautogui.size()

    prev_time = 0
    last_action_time = 0
    last_scroll_time = 0
    smoothening = 7
    prev_loc_x, prev_loc_y = 0, 0

    while True:
        if exit_requested:
            break
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame.")
            break

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(rgb)

        if result.multi_hand_landmarks:
            for handLms in result.multi_hand_landmarks:
                mp_draw.draw_landmarks(frame, handLms, mp_hands.HAND_CONNECTIONS)
                lm = handLms.landmark

                # Detect fingers up
                finger_states = fingers_up(lm)
                # print("Fingers:", finger_states)

                current_time = time.time()

                # Check mappings
                for mapping in mappings:
                    if mapping["gesture"] == finger_states:
                        last_action_time, last_scroll_time = handle_action(
                            mapping["action"], current_time, last_action_time, last_scroll_time, scroll_speed)
                        break

                # Move cursor if "move_cursor" gesture detected (e.g. index finger only)
                if any(m["gesture"] == finger_states and m["action"] == "move_cursor" for m in mappings):
                    index_finger_tip = lm[8]
                    x = int(index_finger_tip.x * screen_w)
                    y = int(index_finger_tip.y * screen_h)

                    # Smooth cursor
                    curr_x = prev_loc_x + (x - prev_loc_x) / smoothening
                    curr_y = prev_loc_y + (y - prev_loc_y) / smoothening
                    pyautogui.moveTo(curr_x, curr_y)
                    prev_loc_x, prev_loc_y = curr_x, curr_y

        # Display
        cv2.putText(frame, "Say 'exit' to quit.", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.imshow("Hand Gesture Control", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("Exiting gesture control...")

if __name__ == "__main__":
    main()