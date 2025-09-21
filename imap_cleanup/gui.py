"""
GUI Application for IMAP Mail Cleanup.

A professional tkinter-based GUI for email cleanup with configuration editing,
progress tracking, and real-time feedback.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import threading
import json
import os
from typing import Dict, Any, Optional
from datetime import datetime

from .gui_interface import GUIInterface, ProcessingCallback
from .config import ConfigManager


class ProgressCallback(ProcessingCallback):
    """Callback implementation for GUI progress updates."""

    def __init__(self, gui_app):
        self.gui_app = gui_app

    def on_start(self, stats: Dict[str, Any]) -> None:
        self.gui_app.on_processing_start(stats)

    def on_folder_start(self, folder: str, total_folders: int, current_folder: int) -> None:
        self.gui_app.on_folder_progress(folder, total_folders, current_folder)

    def on_phase_start(self, phase: str, total_items: int) -> None:
        self.gui_app.on_phase_progress(phase, total_items)

    def on_progress(self, current: int, total: int, message: str = "") -> None:
        self.gui_app.on_item_progress(current, total, message)

    def on_email_processed(self, action: str, uid: str, from_addr: str, subject: str, reason: str) -> None:
        self.gui_app.on_email_result(action, uid, from_addr, subject, reason)

    def on_folder_complete(self, folder: str, candidates: int, moved: int) -> None:
        self.gui_app.on_folder_complete(folder, candidates, moved)

    def on_complete(self, total_candidates: int, total_moved: int) -> None:
        self.gui_app.on_processing_complete(total_candidates, total_moved)

    def on_error(self, error: str, details: str = "") -> None:
        self.gui_app.on_processing_error(error, details)


class ConfigEditor:
    """Configuration editor dialog."""

    def __init__(self, parent, config: Dict[str, Any]):
        self.parent = parent
        self.config = config.copy()
        self.result = None
        self.create_dialog()

    def create_dialog(self):
        """Create the configuration editor dialog."""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Configuration Editor")
        self.dialog.geometry("800x600")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()

        # Create notebook for tabs
        notebook = ttk.Notebook(self.dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Mail Settings Tab
        self.create_mail_settings_tab(notebook)

        # Cleanup Settings Tab
        self.create_cleanup_settings_tab(notebook)

        # Keywords Tab
        self.create_keywords_tab(notebook)

        # Whitelist Tab
        self.create_whitelist_tab(notebook)

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(button_frame, text="Save", command=self.save_config).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT)

    def create_mail_settings_tab(self, notebook):
        """Create mail settings tab."""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Mail Settings")

        mail_settings = self.config["mail_settings"]

        # IMAP Host
        ttk.Label(frame, text="IMAP Host:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.imap_host_var = tk.StringVar(value=mail_settings["imap_host"])
        ttk.Entry(frame, textvariable=self.imap_host_var, width=30).grid(row=0, column=1, padx=5, pady=5)

        # IMAP Port
        ttk.Label(frame, text="IMAP Port:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.imap_port_var = tk.IntVar(value=mail_settings["imap_port"])
        ttk.Entry(frame, textvariable=self.imap_port_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)

        # Source Folders
        ttk.Label(frame, text="Source Folders:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.source_folders_var = tk.StringVar(value=", ".join(mail_settings["source_folders"]))
        ttk.Entry(frame, textvariable=self.source_folders_var, width=50).grid(row=2, column=1, padx=5, pady=5)

        # Target Folder
        ttk.Label(frame, text="Target Folder:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.target_folder_var = tk.StringVar(value=mail_settings["target_folder"])
        ttk.Entry(frame, textvariable=self.target_folder_var, width=30).grid(row=3, column=1, padx=5, pady=5)

    def create_cleanup_settings_tab(self, notebook):
        """Create cleanup settings tab."""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Cleanup Settings")

        cleanup_settings = self.config["cleanup_settings"]

        # Age Days
        ttk.Label(frame, text="Age Days (only process emails older than):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.age_days_var = tk.IntVar(value=cleanup_settings["age_days"])
        ttk.Entry(frame, textvariable=self.age_days_var, width=10).grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)

        # Dry Run
        self.dry_run_var = tk.BooleanVar(value=cleanup_settings["dry_run"])
        ttk.Checkbutton(frame, text="Dry Run (test mode - don't actually move emails)",
                       variable=self.dry_run_var).grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)

        # Verbose
        self.verbose_var = tk.BooleanVar(value=cleanup_settings["verbose"])
        ttk.Checkbutton(frame, text="Verbose logging",
                       variable=self.verbose_var).grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)

        # Max Workers
        ttk.Label(frame, text="Max Workers (use 'auto' for automatic):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.max_workers_var = tk.StringVar(value=str(cleanup_settings["max_workers"]))
        ttk.Entry(frame, textvariable=self.max_workers_var, width=10).grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)

        # Batch Size
        ttk.Label(frame, text="Batch Size:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.batch_size_var = tk.IntVar(value=cleanup_settings["batch_size"])
        ttk.Entry(frame, textvariable=self.batch_size_var, width=10).grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)

    def create_keywords_tab(self, notebook):
        """Create keywords tab."""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Keywords")

        # Subject Keywords
        ttk.Label(frame, text="Subject Keywords (one per line):").pack(anchor=tk.W, padx=5, pady=5)
        self.subject_keywords_text = scrolledtext.ScrolledText(frame, height=10, width=60)
        self.subject_keywords_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.subject_keywords_text.insert(tk.END, "\n".join(self.config["subject_keywords"]))

        # Protect Keywords
        ttk.Label(frame, text="Protect Keywords (prevent moving these emails):").pack(anchor=tk.W, padx=5, pady=5)
        self.protect_keywords_text = scrolledtext.ScrolledText(frame, height=6, width=60)
        self.protect_keywords_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.protect_keywords_text.insert(tk.END, "\n".join(self.config["protect_keywords"]))

    def create_whitelist_tab(self, notebook):
        """Create whitelist tab."""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Whitelist & Domains")

        # Additional Whitelist
        ttk.Label(frame, text="Additional Whitelist (email addresses or domains, one per line):").pack(anchor=tk.W, padx=5, pady=5)
        self.additional_whitelist_text = scrolledtext.ScrolledText(frame, height=8, width=60)
        self.additional_whitelist_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.additional_whitelist_text.insert(tk.END, "\n".join(self.config["whitelist_settings"]["additional_whitelist"]))

        # Delete Domains
        ttk.Label(frame, text="Delete Domains (automatically move emails from these domains):").pack(anchor=tk.W, padx=5, pady=5)
        self.delete_domains_text = scrolledtext.ScrolledText(frame, height=6, width=60)
        self.delete_domains_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.delete_domains_text.insert(tk.END, "\n".join(self.config["delete_domains"]))

    def save_config(self):
        """Save the configuration changes."""
        try:
            # Update mail settings
            self.config["mail_settings"]["imap_host"] = self.imap_host_var.get()
            self.config["mail_settings"]["imap_port"] = self.imap_port_var.get()
            self.config["mail_settings"]["source_folders"] = [f.strip() for f in self.source_folders_var.get().split(",")]
            self.config["mail_settings"]["target_folder"] = self.target_folder_var.get()

            # Update cleanup settings
            self.config["cleanup_settings"]["age_days"] = self.age_days_var.get()
            self.config["cleanup_settings"]["dry_run"] = self.dry_run_var.get()
            self.config["cleanup_settings"]["verbose"] = self.verbose_var.get()
            self.config["cleanup_settings"]["batch_size"] = self.batch_size_var.get()

            # Handle max_workers (can be "auto" or integer)
            max_workers_str = self.max_workers_var.get().strip()
            if max_workers_str.lower() == "auto":
                self.config["cleanup_settings"]["max_workers"] = "auto"
            else:
                self.config["cleanup_settings"]["max_workers"] = int(max_workers_str)

            # Update keywords
            subject_keywords = [kw.strip() for kw in self.subject_keywords_text.get(1.0, tk.END).split("\n") if kw.strip()]
            protect_keywords = [kw.strip() for kw in self.protect_keywords_text.get(1.0, tk.END).split("\n") if kw.strip()]
            self.config["subject_keywords"] = subject_keywords
            self.config["protect_keywords"] = protect_keywords

            # Update whitelist and domains
            additional_whitelist = [item.strip() for item in self.additional_whitelist_text.get(1.0, tk.END).split("\n") if item.strip()]
            delete_domains = [domain.strip() for domain in self.delete_domains_text.get(1.0, tk.END).split("\n") if domain.strip()]
            self.config["whitelist_settings"]["additional_whitelist"] = additional_whitelist
            self.config["delete_domains"] = delete_domains

            self.result = self.config
            self.dialog.destroy()

        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Please check your input values:\n{e}")


class IMAPCleanupGUI:
    """Main GUI application for IMAP Mail Cleanup."""

    def __init__(self):
        self.gui_interface = GUIInterface()
        self.processing = False

        # Processing state tracking
        self.processing_start_time = None
        self.current_folder = ""
        self.current_phase = ""
        self.total_folders = 0
        self.current_folder_index = 0
        self.emails_processed = 0
        self.emails_moved = 0
        self.emails_skipped = 0
        self.phase_start_time = None

        self.create_main_window()

    def create_main_window(self):
        """Create the main application window."""
        self.root = tk.Tk()
        self.root.title("IMAP Mail Cleanup")
        self.root.geometry("900x700")

        # Create menu
        self.create_menu()

        # Create main interface
        self.create_interface()

        # Load initial configuration
        self.refresh_config_display()

    def create_menu(self):
        """Create the application menu."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Load Configuration...", command=self.load_config_file)
        file_menu.add_command(label="Save Configuration...", command=self.save_config_file)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)

        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Configuration...", command=self.edit_config)
        edit_menu.add_command(label="Test Connection", command=self.test_connection)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)

    def create_interface(self):
        """Create the main interface."""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Main tab
        self.create_main_tab()

        # Configuration tab
        self.create_config_tab()

        # Log tab
        self.create_log_tab()

    def create_main_tab(self):
        """Create the main processing tab."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Email Cleanup")

        # Status section
        status_frame = ttk.LabelFrame(frame, text="Status", padding=10)
        status_frame.pack(fill=tk.X, padx=5, pady=5)

        self.status_label = ttk.Label(status_frame, text="Ready", font=("TkDefaultFont", 10, "bold"))
        self.status_label.pack(anchor=tk.W)

        self.connection_label = ttk.Label(status_frame, text="Connection: Not tested")
        self.connection_label.pack(anchor=tk.W)

        # Progress section
        progress_frame = ttk.LabelFrame(frame, text="Progress", padding=10)
        progress_frame.pack(fill=tk.X, padx=5, pady=5)

        # Current operation
        self.operation_label = ttk.Label(progress_frame, text="No operation in progress", font=("TkDefaultFont", 9, "bold"))
        self.operation_label.pack(anchor=tk.W)

        # Overall progress
        progress_container = ttk.Frame(progress_frame)
        progress_container.pack(fill=tk.X, pady=(5, 0))

        ttk.Label(progress_container, text="Overall:").pack(side=tk.LEFT)
        self.overall_progress_bar = ttk.Progressbar(progress_container, mode='determinate')
        self.overall_progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 10))

        self.overall_percent_label = ttk.Label(progress_container, text="0%", width=5)
        self.overall_percent_label.pack(side=tk.RIGHT)

        # Phase progress
        phase_container = ttk.Frame(progress_frame)
        phase_container.pack(fill=tk.X, pady=(2, 0))

        ttk.Label(phase_container, text="Phase:").pack(side=tk.LEFT)
        self.phase_progress_bar = ttk.Progressbar(phase_container, mode='determinate')
        self.phase_progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 10))

        self.phase_percent_label = ttk.Label(phase_container, text="0%", width=5)
        self.phase_percent_label.pack(side=tk.RIGHT)

        # Progress details
        self.progress_details = ttk.Label(progress_frame, text="", foreground="#666")
        self.progress_details.pack(anchor=tk.W, pady=(5, 0))

        # Statistics
        stats_frame = ttk.Frame(progress_frame)
        stats_frame.pack(fill=tk.X, pady=(5, 0))

        self.stats_label = ttk.Label(stats_frame, text="", foreground="#555")
        self.stats_label.pack(side=tk.LEFT)

        self.speed_label = ttk.Label(stats_frame, text="", foreground="#555")
        self.speed_label.pack(side=tk.RIGHT)

        # Controls section
        controls_frame = ttk.LabelFrame(frame, text="Controls", padding=10)
        controls_frame.pack(fill=tk.X, padx=5, pady=5)

        button_frame = ttk.Frame(controls_frame)
        button_frame.pack(fill=tk.X)

        self.test_connection_btn = ttk.Button(button_frame, text="Test Connection", command=self.test_connection)
        self.test_connection_btn.pack(side=tk.LEFT, padx=5)

        self.start_btn = ttk.Button(button_frame, text="Start Cleanup", command=self.start_processing)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = ttk.Button(button_frame, text="Stop", command=self.stop_processing, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        # Results section
        results_frame = ttk.LabelFrame(frame, text="Results", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.results_text = scrolledtext.ScrolledText(results_frame, height=15)
        self.results_text.pack(fill=tk.BOTH, expand=True)

    def create_config_tab(self):
        """Create the configuration overview tab."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Configuration")

        # Configuration display
        config_frame = ttk.LabelFrame(frame, text="Current Configuration", padding=10)
        config_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.config_text = scrolledtext.ScrolledText(config_frame, height=20)
        self.config_text.pack(fill=tk.BOTH, expand=True)

        # Buttons
        button_frame = ttk.Frame(config_frame)
        button_frame.pack(fill=tk.X, pady=5)

        ttk.Button(button_frame, text="Edit Configuration", command=self.edit_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh", command=self.refresh_config_display).pack(side=tk.LEFT, padx=5)

    def create_log_tab(self):
        """Create the log tab."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Log")

        log_frame = ttk.LabelFrame(frame, text="Application Log", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=25)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Buttons
        button_frame = ttk.Frame(log_frame)
        button_frame.pack(fill=tk.X, pady=5)

        ttk.Button(button_frame, text="Clear Log", command=self.clear_log).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Save Log...", command=self.save_log).pack(side=tk.LEFT, padx=5)

    def log_message(self, message: str, level: str = "INFO"):
        """Add a message to the log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {level}: {message}\n"

        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)

        # Also show in results if it's processing-related
        if level in ["PROCESSING", "RESULT"]:
            self.results_text.insert(tk.END, f"{message}\n")
            self.results_text.see(tk.END)

    def refresh_config_display(self):
        """Refresh the configuration display."""
        config = self.gui_interface.get_config()
        self.config_text.delete(1.0, tk.END)
        self.config_text.insert(tk.END, json.dumps(config, indent=2))

    def edit_config(self):
        """Open the configuration editor."""
        config = self.gui_interface.get_config()
        editor = ConfigEditor(self.root, config)
        self.root.wait_window(editor.dialog)

        if editor.result:
            self.gui_interface.update_config(editor.result)
            self.refresh_config_display()
            self.log_message("Configuration updated")

    def test_connection(self):
        """Test the IMAP connection."""
        self.log_message("Testing IMAP connection...")
        self.connection_label.config(text="Connection: Testing...")

        def test_in_thread():
            success, message = self.gui_interface.test_connection()

            # Update UI in main thread
            self.root.after(0, self.update_connection_result, success, message)

        threading.Thread(target=test_in_thread, daemon=True).start()

    def update_connection_result(self, success: bool, message: str):
        """Update connection test result in UI."""
        if success:
            self.connection_label.config(text="Connection: ✓ Success")
            self.log_message(f"Connection test successful: {message}")
        else:
            self.connection_label.config(text="Connection: ✗ Failed")
            self.log_message(f"Connection test failed: {message}", "ERROR")
            messagebox.showerror("Connection Failed", f"Could not connect to IMAP server:\n{message}")

    def start_processing(self):
        """Start the email processing."""
        if self.processing:
            return

        self.processing = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_label.config(text="Processing...")

        self.results_text.delete(1.0, tk.END)
        self.log_message("Starting email cleanup processing", "PROCESSING")

        callback = ProgressCallback(self)
        success = self.gui_interface.start_processing(callback)

        if not success:
            self.processing = False
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            self.status_label.config(text="Ready")
            messagebox.showerror("Error", "Could not start processing. Check your configuration and connection.")

    def stop_processing(self):
        """Stop the email processing."""
        self.gui_interface.stop_processing()
        self.log_message("Stop requested", "PROCESSING")

    def on_processing_start(self, stats: Dict[str, Any]):
        """Handle processing start."""
        import time
        self.processing_start_time = time.time()
        self.emails_processed = 0
        self.emails_moved = 0
        self.emails_skipped = 0

        self.log_message(f"Processing started with {stats['max_workers']} workers + {stats.get('header_fetch_workers', 0)} header workers", "PROCESSING")

        # Reset progress bars
        self.overall_progress_bar.config(value=0)
        self.phase_progress_bar.config(value=0)
        self.overall_percent_label.config(text="0%")
        self.phase_percent_label.config(text="0%")

        # Update operation status
        self.operation_label.config(text="Starting email cleanup...")
        self.progress_details.config(text="Initializing connection and folders...")
        self.update_stats_display()

    def on_folder_progress(self, folder: str, total_folders: int, current_folder: int):
        """Handle folder progress."""
        self.current_folder = folder
        self.total_folders = total_folders
        self.current_folder_index = current_folder

        # Update overall progress based on folder completion
        if total_folders > 0:
            overall_progress = ((current_folder - 1) / total_folders) * 100
            self.overall_progress_bar.config(value=overall_progress)
            self.overall_percent_label.config(text=f"{overall_progress:.0f}%")

        self.operation_label.config(text=f"Processing folder {current_folder}/{total_folders}: {folder}")
        self.progress_details.config(text="Searching for candidate emails...")

        # Reset phase progress for new folder
        self.phase_progress_bar.config(value=0)
        self.phase_percent_label.config(text="0%")

    def on_phase_progress(self, phase: str, total_items: int):
        """Handle phase progress."""
        import time
        self.current_phase = phase
        self.phase_start_time = time.time()

        # Update phase display
        self.progress_details.config(text=f"{phase} - {total_items} items")

        # Reset phase progress bar
        self.phase_progress_bar.config(value=0)
        self.phase_percent_label.config(text="0%")

        # Log phase start
        self.log_message(f"Starting {phase.lower()} for {total_items} items", "PROCESSING")

    def on_item_progress(self, current: int, total: int, message: str = ""):
        """Handle item progress."""
        if total > 0:
            # Update phase progress
            phase_progress = (current / total) * 100
            self.phase_progress_bar.config(value=phase_progress)
            self.phase_percent_label.config(text=f"{phase_progress:.0f}%")

            # Update details with current item info
            detail_text = f"{self.current_phase} - {current}/{total}"
            if message:
                detail_text += f" - {message}"
            self.progress_details.config(text=detail_text)

            # Update processing speed
            self.update_speed_display(current, total)

    def on_email_result(self, action: str, uid: str, from_addr: str, subject: str, reason: str):
        """Handle email processing result."""
        self.emails_processed += 1

        if action == "moved":
            self.emails_moved += 1
            self.log_message(f"✓ Moved: {from_addr} | {reason}", "RESULT")
        elif action == "skip":
            self.emails_skipped += 1
            self.log_message(f"⏭ Skipped: {from_addr} | {reason}", "RESULT")

        # Update stats display
        self.update_stats_display()

    def on_folder_complete(self, folder: str, candidates: int, moved: int):
        """Handle folder completion."""
        # Update overall progress
        if self.total_folders > 0:
            overall_progress = (self.current_folder_index / self.total_folders) * 100
            self.overall_progress_bar.config(value=overall_progress)
            self.overall_percent_label.config(text=f"{overall_progress:.0f}%")

        self.log_message(f"✅ Folder '{folder}' complete: {candidates} candidates, {moved} moved", "PROCESSING")

    def on_processing_complete(self, total_candidates: int, total_moved: int):
        """Handle processing completion."""
        import time

        self.processing = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_label.config(text="Completed")

        # Set progress bars to 100%
        self.overall_progress_bar.config(value=100)
        self.phase_progress_bar.config(value=100)
        self.overall_percent_label.config(text="100%")
        self.phase_percent_label.config(text="100%")

        # Calculate total time
        if self.processing_start_time:
            total_time = time.time() - self.processing_start_time
            time_str = f"{int(total_time // 60)}m {int(total_time % 60)}s"
        else:
            time_str = "unknown"

        # Update final status
        self.operation_label.config(text="Processing completed successfully")
        self.progress_details.config(text=f"Finished in {time_str}")

        # Final stats update
        self.update_stats_display()
        self.speed_label.config(text=f"Completed in {time_str}")

        message = f"Processing complete!\n\nProcessed: {total_candidates} emails\nMoved: {total_moved} emails\nTime: {time_str}"
        self.log_message(f"🎉 {message.replace(chr(10), ' ')}", "PROCESSING")
        messagebox.showinfo("Processing Complete", message)

    def on_processing_error(self, error: str, details: str = ""):
        """Handle processing error."""
        self.processing = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_label.config(text="Error")

        self.log_message(f"Error: {error}", "ERROR")
        if details:
            self.log_message(f"Details: {details}", "ERROR")

        messagebox.showerror("Processing Error", f"An error occurred:\n{error}")

    def update_stats_display(self):
        """Update the statistics display."""
        stats_text = f"Processed: {self.emails_processed} | Moved: {self.emails_moved} | Skipped: {self.emails_skipped}"
        self.stats_label.config(text=stats_text)

    def update_speed_display(self, current: int, total: int):
        """Update the processing speed display."""
        if not self.phase_start_time or current == 0:
            return

        import time
        elapsed = time.time() - self.phase_start_time
        if elapsed > 0:
            items_per_sec = current / elapsed
            if items_per_sec > 0:
                eta_seconds = (total - current) / items_per_sec
                if eta_seconds < 60:
                    eta_str = f"{int(eta_seconds)}s"
                else:
                    eta_str = f"{int(eta_seconds // 60)}m {int(eta_seconds % 60)}s"

                speed_text = f"{items_per_sec:.1f} items/s | ETA: {eta_str}"
                self.speed_label.config(text=speed_text)

    def load_config_file(self):
        """Load configuration from file."""
        filename = filedialog.askopenfilename(
            title="Load Configuration",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'r') as f:
                    config = json.load(f)
                self.gui_interface.update_config(config)
                self.refresh_config_display()
                self.log_message(f"Configuration loaded from {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not load configuration:\n{e}")

    def save_config_file(self):
        """Save configuration to file."""
        filename = filedialog.asksaveasfilename(
            title="Save Configuration",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            try:
                config = self.gui_interface.get_config()
                with open(filename, 'w') as f:
                    json.dump(config, f, indent=2)
                self.log_message(f"Configuration saved to {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not save configuration:\n{e}")

    def clear_log(self):
        """Clear the log."""
        self.log_text.delete(1.0, tk.END)

    def save_log(self):
        """Save log to file."""
        filename = filedialog.asksaveasfilename(
            title="Save Log",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write(self.log_text.get(1.0, tk.END))
                self.log_message(f"Log saved to {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not save log:\n{e}")

    def show_about(self):
        """Show about dialog."""
        about_text = """IMAP Mail Cleanup v2.0.0

A professional, threaded email cleanup tool for iCloud IMAP.

Features:
• Multi-threaded processing with auto CPU detection
• Safe operation with dry-run mode
• Configurable email detection and protection
• GUI interface with real-time progress
• Comprehensive logging and error handling

Generated with Claude Code
https://claude.ai/code
"""
        messagebox.showinfo("About", about_text)

    def run(self):
        """Run the GUI application."""
        self.log_message("IMAP Mail Cleanup GUI started")
        self.root.mainloop()


def main():
    """Main entry point for GUI application."""
    app = IMAPCleanupGUI()
    app.run()


if __name__ == "__main__":
    main()