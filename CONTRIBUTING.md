# Contributing to Accu-Chek Active Platform

Thank you for your interest in contributing to this open-source project!

## Guiding Principles & Safety Rules

> ⚠️ **CRITICAL MEDICAL SAFETY RULE: READ-ONLY COMMUNICATION**
> This project adheres to a strict read-only policy when communicating with medical hardware.
> Under **NO circumstances** should PRs introduce commands that write to meter memory, attempt firmware flashing, or modify device calibration.
> The only permitted APDUs are association negotiation (`E2`/`E3`/`E4`), attribute queries (`01 03`), segment read requests (`0C 0D` / `0C 1C`), and acknowledgement ACKs (`02 01`).
> Never send `SET_TIME` (`0C 17`) or destructive `ABORT` sequences.

## Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/accu-chek-active-platform.git
   cd accu-chek-active-platform
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Linux/macOS
   # or
   venv\Scripts\activate     # On Windows
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run Unit Tests:**
   ```bash
   # On Windows
   cmd /c "set PYTHONPATH=core && python -m pytest core/tests"

   # On Linux
   PYTHONPATH=core pytest core/tests
   ```

5. **Start the Development Server:**
   ```bash
   python server.py
   ```
   Open `http://localhost:5050` in your browser.

## Submitting Pull Requests

1. Fork the repository.
2. Create your feature branch (`git checkout -b feature/amazing-feature`).
3. Ensure all tests pass.
4. Commit your changes (`git commit -m 'feat: add amazing feature'`).
5. Push to the branch (`git push origin feature/amazing-feature`).
6. Open a Pull Request.
