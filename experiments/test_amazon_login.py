#!/usr/bin/env python3
"""Test script for Amazon passkey authentication with run tracking.

This experiment tests the complete login flow and captures screenshots
at each step for visualization in the web UI.

Usage:
    python experiments/test_amazon_login.py [--email EMAIL] [--headless]

Requirements:
    - UI-Agent running on http://localhost:8000
    - Shopping-Agent running on http://localhost:8080 (for web UI)
    - YubiKey with passkey configured for Amazon
    - ydotool installed and running (for PIN input on Wayland)
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from app.logging import get_run_tracker, RunStatus


# Configuration
UI_AGENT_URL = "http://localhost:8000"
AMAZON_LOGIN_URL = "https://www.amazon.in/ap/signin?openid.pape.max_auth_age=0&openid.return_to=https%3A%2F%2Fwww.amazon.in%2F&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.assoc_handle=inflex&openid.mode=checkid_setup&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0"


class AmazonLoginExperiment:
    """Experiment runner for Amazon login with passkey."""

    def __init__(self, email: str, headless: bool = False):
        self.email = email
        self.headless = headless
        self.tracker = get_run_tracker()
        self.http_client = httpx.AsyncClient(base_url=UI_AGENT_URL, timeout=60.0)
        self.run = None

    async def close(self):
        """Clean up resources."""
        await self.http_client.aclose()
        await self.tracker.close()

    async def take_screenshot(self, name: str = "screenshot") -> str | None:
        """Take a screenshot and save it to the run directory."""
        if not self.run:
            return None
        return await self.tracker.capture_screenshot(self.run.id, name=name)

    async def navigate(self, url: str, wait_until: str = "networkidle") -> dict:
        """Navigate browser to URL."""
        response = await self.http_client.post(
            "/browser/navigate",
            json={"url": url, "wait_until": wait_until}
        )
        return response.json()

    async def fill(self, selector: str, value: str) -> dict:
        """Fill a form field."""
        response = await self.http_client.post(
            "/browser/fill",
            json={"selector": selector, "value": value}
        )
        return response.json()

    async def click(self, selector: str) -> dict:
        """Click an element."""
        response = await self.http_client.post(
            "/browser/click",
            json={"selector": selector}
        )
        return response.json()

    async def wait_for(self, selector: str, timeout: int = 10000) -> dict:
        """Wait for an element to appear."""
        response = await self.http_client.post(
            "/browser/wait",
            json={"selector": selector, "timeout": timeout}
        )
        return response.json()

    async def get_content(self) -> dict:
        """Get page content."""
        response = await self.http_client.get("/browser/content")
        return response.json()

    async def start_passkey_flow(self) -> dict:
        """Start the passkey authentication flow via API."""
        response = await self.http_client.post(
            "/auth/passkey/start",
            json={
                "url": AMAZON_LOGIN_URL,
                "email": self.email,
                "site": "amazon",
            }
        )
        return response.json()

    async def submit_pin(self, pin: str) -> dict:
        """Submit PIN for passkey authentication."""
        response = await self.http_client.post(
            "/auth/passkey/pin",
            json={"pin": pin}
        )
        return response.json()

    async def run_experiment(self) -> bool:
        """Run the complete login experiment.

        Returns:
            True if successful, False otherwise
        """
        # Create run
        self.run = self.tracker.create_run(
            name="Amazon Login - Passkey Auth",
            description=f"Testing passkey login for {self.email}",
            platform="amazon",
            metadata={"email": self.email, "headless": self.headless},
        )
        self.tracker.start_run(self.run.id)

        print(f"\n{'='*60}")
        print(f"Starting Amazon Login Experiment (Run #{self.run.id})")
        print(f"Email: {self.email}")
        print(f"View progress at: http://localhost:8080/runs")
        print(f"{'='*60}\n")

        success = False
        error_message = None

        try:
            # Step 1: Ensure browser is started
            step1 = self.tracker.add_step(
                self.run.id,
                "Start Browser",
                description="Ensure browser is running in non-headless mode"
            )
            self.tracker.start_step(step1.id)

            try:
                response = await self.http_client.post(
                    "/browser/start",
                    params={"headless": self.headless}
                )
                result = response.json()
                print(f"[1/6] Browser status: {result.get('status', 'unknown')}")
                screenshot = await self.take_screenshot("browser_started")
                self.tracker.complete_step(step1.id, success=True, screenshot_path=screenshot)
            except Exception as e:
                self.tracker.complete_step(step1.id, success=False, error_message=str(e))
                raise

            # Step 2: Navigate to Amazon login
            step2 = self.tracker.add_step(
                self.run.id,
                "Navigate to Login",
                description="Open Amazon sign-in page"
            )
            self.tracker.start_step(step2.id)

            try:
                await self.navigate(AMAZON_LOGIN_URL)
                await asyncio.sleep(2)
                screenshot = await self.take_screenshot("login_page")
                print(f"[2/6] Navigated to Amazon login page")
                self.tracker.complete_step(step2.id, success=True, screenshot_path=screenshot)
            except Exception as e:
                screenshot = await self.take_screenshot("login_error")
                self.tracker.complete_step(step2.id, success=False, error_message=str(e), screenshot_path=screenshot)
                raise

            # Step 3: Enter email
            step3 = self.tracker.add_step(
                self.run.id,
                "Enter Email",
                description=f"Fill email field with {self.email}"
            )
            self.tracker.start_step(step3.id)

            try:
                await self.fill("#ap_email", self.email)
                await asyncio.sleep(0.5)
                screenshot = await self.take_screenshot("email_entered")
                print(f"[3/6] Email entered: {self.email}")
                self.tracker.complete_step(step3.id, success=True, screenshot_path=screenshot)
            except Exception as e:
                screenshot = await self.take_screenshot("email_error")
                self.tracker.complete_step(step3.id, success=False, error_message=str(e), screenshot_path=screenshot)
                raise

            # Step 4: Click Continue
            step4 = self.tracker.add_step(
                self.run.id,
                "Click Continue",
                description="Click the Continue button to proceed"
            )
            self.tracker.start_step(step4.id)

            try:
                await self.click("#continue")
                await asyncio.sleep(2)
                screenshot = await self.take_screenshot("after_continue")
                print(f"[4/6] Clicked Continue")
                self.tracker.complete_step(step4.id, success=True, screenshot_path=screenshot)
            except Exception as e:
                screenshot = await self.take_screenshot("continue_error")
                self.tracker.complete_step(step4.id, success=False, error_message=str(e), screenshot_path=screenshot)
                raise

            # Step 5: Click Passkey button
            step5 = self.tracker.add_step(
                self.run.id,
                "Click Passkey Button",
                description="Click 'Sign in with passkey' button"
            )
            self.tracker.start_step(step5.id)

            try:
                # Wait for passkey button to appear
                result = await self.wait_for("#auth-signin-passkey-btn", timeout=10000)
                if not result.get("found"):
                    raise Exception("Passkey button not found")

                await self.click("#auth-signin-passkey-btn")
                await asyncio.sleep(2)
                screenshot = await self.take_screenshot("passkey_clicked")
                print(f"[5/6] Clicked passkey button - waiting for PIN input")
                self.tracker.complete_step(step5.id, success=True, screenshot_path=screenshot)
            except Exception as e:
                screenshot = await self.take_screenshot("passkey_error")
                self.tracker.complete_step(step5.id, success=False, error_message=str(e), screenshot_path=screenshot)
                raise

            # Step 6: PIN Entry (manual)
            step6 = self.tracker.add_step(
                self.run.id,
                "Enter PIN & Touch Key",
                description="Enter YubiKey PIN and touch the security key"
            )
            self.tracker.start_step(step6.id)

            try:
                print("\n" + "="*60)
                print("MANUAL ACTION REQUIRED:")
                print("1. A PIN dialog should appear in the browser")
                print("2. Enter your YubiKey PIN in the dialog")
                print("3. Touch your YubiKey when it blinks")
                print("="*60)

                # Option 1: Use the API endpoint (if running headless)
                # pin = input("\nEnter YubiKey PIN (or press Enter if using API): ")
                # if pin:
                #     result = await self.submit_pin(pin)

                # Option 2: Wait for manual completion
                print("\nWaiting 30 seconds for authentication to complete...")
                for i in range(30):
                    await asyncio.sleep(1)
                    # Check if we've navigated away from login page
                    content = await self.get_content()
                    url = content.get("url", "")
                    if "amazon.in/ap/signin" not in url and "amazon.in" in url:
                        print(f"  -> Detected successful login!")
                        break
                    print(f"  Waiting... ({30-i}s remaining)")

                screenshot = await self.take_screenshot("after_auth")

                # Check final state
                content = await self.get_content()
                final_url = content.get("url", "")

                if "amazon.in/ap/signin" not in final_url:
                    print(f"[6/6] Authentication successful!")
                    print(f"  -> Redirected to: {final_url[:80]}...")
                    self.tracker.complete_step(step6.id, success=True, screenshot_path=screenshot)
                    success = True
                else:
                    print(f"[6/6] Authentication may have failed - still on login page")
                    self.tracker.complete_step(
                        step6.id,
                        success=False,
                        error_message="Still on login page after timeout",
                        screenshot_path=screenshot
                    )

            except Exception as e:
                screenshot = await self.take_screenshot("auth_error")
                self.tracker.complete_step(step6.id, success=False, error_message=str(e), screenshot_path=screenshot)
                raise

        except Exception as e:
            error_message = str(e)
            print(f"\nExperiment failed: {error_message}")

        # Complete run
        self.tracker.complete_run(self.run.id, success=success, error_message=error_message)

        print(f"\n{'='*60}")
        print(f"Experiment {'PASSED' if success else 'FAILED'}")
        print(f"View results at: http://localhost:8080/runs")
        print(f"Run ID: {self.run.id}")
        print(f"{'='*60}\n")

        return success


async def main():
    parser = argparse.ArgumentParser(description="Test Amazon passkey login")
    parser.add_argument(
        "--email",
        default="mail.prabhanshu@gmail.com",
        help="Email address for login"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode (not recommended for passkey)"
    )
    args = parser.parse_args()

    # Check if UI-Agent is running
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{UI_AGENT_URL}/health", timeout=5.0)
            if response.status_code != 200:
                print(f"ERROR: UI-Agent not healthy at {UI_AGENT_URL}")
                sys.exit(1)
    except Exception as e:
        print(f"ERROR: Cannot connect to UI-Agent at {UI_AGENT_URL}")
        print(f"  Make sure UI-Agent is running: cd UI-agent && uv run uvicorn src.api.server:app")
        sys.exit(1)

    experiment = AmazonLoginExperiment(email=args.email, headless=args.headless)

    try:
        success = await experiment.run_experiment()
        sys.exit(0 if success else 1)
    finally:
        await experiment.close()


if __name__ == "__main__":
    asyncio.run(main())
