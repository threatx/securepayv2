# AI-Assisted Development Notice
# This file was entirely generated with AI assistance using Claude Code CLI (Anthropic, 2026).
# AI was used for: complete code generation
# Student contribution: requirements specification, target source identification, output format definition, testing
# Reference: Anthropic. (2026). Claude Code CLI (Claude Opus 4 / Sonnet 4) [Large language model].
#            https://claude.ai/claude-code

import json
import os
import re
import requests
from groq import Groq
import cohere


class OllamaFraudVerifier:
    """Verify if a complaint is a UPI-related fraud/scam using local Ollama (no API limits!)."""

    PROMPT = """Analyze this consumer complaint and determine if it describes a UPI-related fraud or scam.

COMPLAINT:
Title: {title}
Text: {raw_text}

Respond ONLY with valid JSON (no markdown, no explanation):
{{"is_fraud": true or false, "is_upi_related": true or false, "fraud_type": "job_scam" | "phishing" | "account_hack" | "fake_seller" | "impersonation" | "investment_scam" | "qr_code_scam" | "collect_request_scam" | "other_fraud" | null, "confidence": "high" | "medium" | "low"}}

is_upi_related=TRUE only if payment was via UPI apps (GPay, PhonePe, Paytm, BHIM) or UPI ID.
is_fraud=TRUE if victim was DECEIVED by a bad actor."""

    def __init__(self, model: str = "llama3.2:3b"):
        self.model = model
        self.base_url = "http://localhost:11434"

    def verify(self, title: str, raw_text: str) -> dict:
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": self.PROMPT.format(title=title, raw_text=raw_text[:2000]),
                    "stream": False
                },
                timeout=60
            )
            response.raise_for_status()
            text = response.json().get("response", "")
            # Remove markdown code blocks if present
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            # Find JSON in response
            start = text.find('{')
            end = text.rfind('}') + 1
            if start >= 0 and end > start:
                text = text[start:end]
            result = json.loads(text.strip())
            return {
                "is_fraud": result.get("is_fraud", False),
                "is_upi_related": result.get("is_upi_related", False),
                "fraud_type": result.get("fraud_type"),
                "confidence": result.get("confidence", "low"),
                "reason": ""
            }
        except Exception as e:
            return {
                "is_fraud": False,
                "is_upi_related": False,
                "fraud_type": None,
                "confidence": "low",
                "reason": f"Ollama error: {str(e)}"
            }


class CohereFraudVerifier:
    """Verify if a complaint is a UPI-related fraud/scam using Cohere API."""

    PROMPT = """Analyze this consumer complaint and determine if it describes a UPI-related fraud or scam.

COMPLAINT:
Title: {title}
Text: {raw_text}

Respond ONLY with valid JSON (no markdown, no code blocks):
{{"is_fraud": true or false, "is_upi_related": true or false, "fraud_type": "job_scam" | "phishing" | "account_hack" | "fake_seller" | "impersonation" | "investment_scam" | "qr_code_scam" | "collect_request_scam" | "other_fraud" | null, "confidence": "high" | "medium" | "low"}}

is_upi_related=TRUE only if payment was via UPI apps (GPay, PhonePe, Paytm, BHIM) or UPI ID.
is_fraud=TRUE if victim was DECEIVED by a bad actor."""

    def __init__(self):
        api_key = os.environ.get('COHERE_API_KEY')
        if not api_key:
            raise ValueError("COHERE_API_KEY not set")
        self.client = cohere.ClientV2(api_key)

    def verify(self, title: str, raw_text: str) -> dict:
        try:
            response = self.client.chat(
                model="command-a-03-2025",
                messages=[{"role": "user", "content": self.PROMPT.format(title=title, raw_text=raw_text[:2000])}]
            )
            text = response.message.content[0].text
            # Remove markdown code blocks if present
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            result = json.loads(text.strip())
            return {
                "is_fraud": result.get("is_fraud", False),
                "is_upi_related": result.get("is_upi_related", False),
                "fraud_type": result.get("fraud_type"),
                "confidence": result.get("confidence", "low"),
                "reason": ""
            }
        except Exception as e:
            return {
                "is_fraud": False,
                "is_upi_related": False,
                "fraud_type": None,
                "confidence": "low",
                "reason": f"API error: {str(e)}"
            }


class FraudVerifier:
    """Verify if a complaint is a UPI-related fraud/scam using Groq (free LLM API)."""

    PROMPT = """Analyze this consumer complaint and determine if it describes a UPI-related fraud or scam.

COMPLAINT:
Title: {title}
Text: {raw_text}

Respond ONLY with valid JSON (no markdown, no explanation outside JSON):
{{
    "is_fraud": true or false,
    "is_upi_related": true or false,
    "fraud_type": "job_scam" | "phishing" | "account_hack" | "fake_seller" | "impersonation" | "investment_scam" | "lottery_scam" | "qr_code_scam" | "collect_request_scam" | "other_fraud" | null,
    "confidence": "high" | "medium" | "low",
    "reason": "brief 1-sentence explanation"
}}

CLASSIFICATION RULES:

1. is_upi_related=TRUE only if payment was made via:
   - UPI apps: GPay, Google Pay, PhonePe, Paytm, BHIM, RazorPay
   - UPI ID (like xyz@upi, xyz@oksbi, xyz@ybl)
   - QR code payment scam
   - UPI collect request scam
   - UPI PIN/OTP stolen

   is_upi_related=FALSE if:
   - Payment via credit card, debit card, net banking, cash, cheque
   - No digital payment involved
   - Only mentions bank name without UPI
   - Insurance, loan, membership payments (unless via UPI)

2. is_fraud=TRUE: Victim was DECEIVED by a bad actor (scammer, hacker, fake seller)

   is_fraud=FALSE: No deception - user error, technical issues, service complaints"""

    def __init__(self):
        # Check for API key
        api_key = os.environ.get('GROQ_API_KEY')
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY not set. Please add it to your .env file:\n"
                "GROQ_API_KEY=your-api-key-here\n"
                "Or run with --no-verify to skip LLM verification."
            )
        self.client = Groq(api_key=api_key)

    def verify(self, title: str, raw_text: str) -> dict:
        """
        Verify if complaint is a UPI-related fraud/scam.

        Returns:
            dict with keys: is_fraud, is_upi_related, fraud_type, confidence, reason
        """
        try:
            response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                max_tokens=250,
                messages=[{
                    "role": "user",
                    "content": self.PROMPT.format(title=title, raw_text=raw_text[:2000])
                }]
            )
            result = json.loads(response.choices[0].message.content)
            return {
                "is_fraud": result.get("is_fraud", False),
                "is_upi_related": result.get("is_upi_related", False),
                "fraud_type": result.get("fraud_type"),
                "confidence": result.get("confidence", "low"),
                "reason": result.get("reason", "")
            }
        except json.JSONDecodeError:
            # If LLM didn't return valid JSON, assume not valid
            return {
                "is_fraud": False,
                "is_upi_related": False,
                "fraud_type": None,
                "confidence": "low",
                "reason": "Failed to parse LLM response"
            }
        except Exception as e:
            # On API error, return uncertain result
            return {
                "is_fraud": False,
                "is_upi_related": False,
                "fraud_type": None,
                "confidence": "low",
                "reason": f"API error: {str(e)}"
            }
