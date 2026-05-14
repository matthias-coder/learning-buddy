-- Phase 14: Keyboard-hint cheat-sheet toggle per user

ALTER TABLE users ADD COLUMN show_keyboard_hints INTEGER NOT NULL DEFAULT 1;
