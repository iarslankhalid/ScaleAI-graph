"""
Claude Client

Handles communication with the Anthropic Claude API.
"""

from typing import Optional
import anthropic
import logging

from config.settings import get_settings
from ..context.assembler import ContextPacket

logger = logging.getLogger(__name__)


class ClaudeClient:
    """
    Client for Claude API.
    
    Usage:
        client = ClaudeClient()
        response = client.generate(context_packet)
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-20250514"):
        """
        Initialize Claude client.
        
        Args:
            api_key: Anthropic API key (defaults to settings)
            model: Model to use (default: claude-sonnet-4-20250514)
        """
        settings = get_settings()
        self.api_key = api_key or settings.anthropic_api_key
        self.model = model
        self.client = None
        
        if self.api_key:
            self.client = anthropic.Anthropic(api_key=self.api_key)
    
    def generate(
        self,
        context: ContextPacket,
        max_tokens: int = 1024,
        temperature: float = 0.3
    ) -> str:
        """
        Generate a response using Claude.
        
        Args:
            context: ContextPacket with system prompt and user content
            max_tokens: Maximum response tokens
            temperature: Response temperature (lower = more focused)
            
        Returns:
            Generated response text
        """
        if not self.client:
            return self._mock_response(context)
        
        try:
            # Build the user message from context
            user_message = context.to_prompt()
            
            # Call Claude API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=context.system_prompt,
                messages=[
                    {"role": "user", "content": user_message}
                ]
            )
            
            # Extract text from response
            if response.content:
                return response.content[0].text
            
            return "No response generated."
            
        except anthropic.APIError as e:
            logger.error(f"Claude API error: {e}")
            return f"Error generating response: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return f"Unexpected error: {str(e)}"
    
    def _mock_response(self, context: ContextPacket) -> str:
        """Generate a mock response when API key is not available"""
        return f"""[MOCK RESPONSE - No API key configured]

Based on the query: "{context.user_query}"

**Dependency Path:**
{context.traversal_path}

**Analysis:**
This is a mock response. To get real responses:
1. Set ANTHROPIC_API_KEY in your .env file
2. Restart the application

**Node Details:**
{context.node_details[:500]}...

---
Configure your API key to enable Claude responses.
"""
    
    def generate_simple(self, prompt: str, max_tokens: int = 512) -> str:
        """
        Simple generation without context packet.
        
        Args:
            prompt: Simple text prompt
            max_tokens: Maximum response tokens
            
        Returns:
            Generated response
        """
        if not self.client:
            return f"[MOCK] Response to: {prompt[:100]}..."
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            if response.content:
                return response.content[0].text
            
            return "No response generated."
            
        except Exception as e:
            logger.error(f"Error: {e}")
            return f"Error: {str(e)}"
