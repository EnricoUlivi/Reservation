# Reservation

A web application built with **Python (Flask)** and vanilla **HTML/CSS/JS** designed to manage room reservations and optimize booking allocations using a custom **Greedy Solver algorithm**.

---

## Project Overview

This project was developed to streamline reservation management and room assignment. It automatically calculates optimal room allocations based on booking requirements, capacity constraints, and gaps between stays.

### Key Features:
- **Interactive Calendar View:** Visual timeline of bookings, check-ins/check-outs, conflicts, and room changeovers.
- **Greedy Optimization Solver:** Automatically assigns bookings to maximize contiguous free days (≥ 5 days) and minimizes room switches.
- **Flexible Constraints Handling:** Supports room floor restrictions (e.g., no attic/mansard, no 4th floor), capacity tiers (Low, Medium, High season), room preferences, and split-room bookings.
- **Checkout & Billing Calculator:** Dynamic itemized billing with custom service rates and extra night calculations.
- **RESTful API Architecture:** Seamless client-server data synchronization backed by lightweight JSON storage.

---

## Tech Stack

| Component | Technologies Used |
| :--- | :--- |
| **Backend** | Python 3, Flask, Custom Solver Algorithm |
| **Frontend** | HTML5, CSS3 (Modern Dark Theme), Vanilla JavaScript (Fetch API) |
| **Storage** | JSON File Persistence (Auto-generating) |
| **Packaging** | PyInstaller (Cross-platform compilation support) |

---

## Getting Started

### Prerequisites
- **Python 3.8+** installed on your system.
- **pip** (Python package manager).

### Installation
1. Clone the repository:
   ```bash
   git clone [https://github.com/EnricoUlivi/prenotazioni.git](https://github.com/EnricoUlivi/prenotazioni.git)
   cd prenotazioni
   Install the required dependencies:
   pip install -r requirements.txt
   ```
Running the Application: Cross-Platform (macOS, Linux, Windows)
Run the Flask application directly with Python:
python app.py
The application will start the local server and automatically open your default browser at http://localhost:8000.
