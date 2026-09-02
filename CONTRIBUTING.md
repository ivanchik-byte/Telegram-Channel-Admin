# Contributing to Telegram Channel Admin

Thank you for your interest in improving Telegram Channel Admin. We welcome contributions from bug fixes and documentation updates to new features and performance improvements.

Please take a moment to review this guide before getting started.

---

## Code of conduct

By participating in this project, you agree to abide by our [Code of conduct](CODE_OF_CONDUCT.md). Please report unacceptable behavior to project maintainers.

---

## Getting started

### Prerequisites

Make sure you have the following tools installed locally:

* Python 3.11 or higher
* Docker and Docker Compose
* Git

### Local environment setup

1. **Fork and clone the repository:**

   ```bash
   git clone https://github.com/<your-username>/Telegram-Channel-Admin.git
   cd Telegram-Channel-Admin
   ```

2. **Create and activate a virtual environment:**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

4. **Configure environment variables:**

   Copy the example environment file and fill in your development credentials:

   ```bash
   cp .env.example .env
   ```

   You need at minimum:
   * `API_ID` and `API_HASH` from https://my.telegram.org
   * `TELEGRAM_BOT_TOKEN` from @BotFather
   * `TARGET_CHANNEL_ID` and `ADMIN_IDS`
   * `AI_API_KEY`, `AI_BASE_URL`, and `AI_MODEL` for AI text rewriting

5. **Start backend services with Docker Compose:**

   Start PostgreSQL and Redis in the background:

   ```bash
   docker compose up -d db redis
   ```

6. **Apply database migrations:**

   ```bash
   alembic upgrade head
   ```

---

## Development workflow

### Branch naming conventions

Create a feature branch from `master` using one of the following prefixes:

* `feat/your-feature-name` for new functionality
* `fix/bug-description` for bug fixes
* `docs/documentation-update` for documentation changes
* `refactor/component-name` for internal refactoring

```bash
git checkout -b feat/custom-prompt-filters
```

### Running tests

Always run tests before submitting a pull request:

```bash
pytest
```

To run a specific test file:

```bash
pytest tests/test_i18n_keys.py
```

### Code style guidelines

* Follow PEP 8 standards for Python code.
* Use explicit type annotations for function parameters and return values.
* Keep functions small and focused on a single responsibility.
* Do not leave commented-out code or debug print statements in committed files.
* Ensure all text intended for Telegram messages uses existing `i18n` keys or adds parity keys in both `ru` and `en` dictionaries in `src/core/i18n.py`.

### Commit message format

We follow the Conventional Commits specification:

```
<type>(<scope>): <short description>
```

Common types:
* `feat`: A new user-facing feature
* `fix`: A bug fix
* `refactor`: Code change that neither fixes a bug nor adds a feature
* `docs`: Documentation only changes
* `test`: Adding or correcting tests
* `chore`: Maintenance tasks, dependency updates, or build configs

Examples:
* `feat(worker): add exponential backoff for AI timeout errors`
* `fix(parser): prevent duplicate channel join attempts`
* `docs(readme): update environment setup instructions`

---

## Submitting a pull request

1. Push your branch to your GitHub fork:

   ```bash
   git push origin feat/your-feature-name
   ```

2. Open a pull request against the `master` branch of the upstream repository.
3. Fill out the pull request template with a summary of changes, motivation, and test results.
4. Ensure the test suite passes.
5. Address any review comments or requested changes promptly.

---

## Questions or need help?

If you have questions about the codebase or architecture, open an issue labeled `question` or join the community discussions.
