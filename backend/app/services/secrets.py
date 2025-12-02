"""Secret Manager Service for Bitwarden integration."""

import asyncio
import json
import re
import subprocess
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from ..config import settings


class SecretManager:
    """
    Manages Bitwarden secret resolution and caching.
    
    Responsibilities:
    - Parse Bitwarden reference notation ({{ bw:item-id:field }})
    - Resolve secrets from Bitwarden Vault
    - Cache secrets in memory during session
    - Ensure secrets are never written to disk
    """

    # Pattern for Bitwarden reference notation: {{ bw:item-id:field }}
    REFERENCE_PATTERN = re.compile(r'\{\{\s*bw:([^:]+):([^}]+)\s*\}\}')

    def __init__(self):
        """Initialize the Secret Manager with empty cache."""
        # Cache structure: {session_id: {cache_key: (value, expiry_time)}}
        self._cache: Dict[str, Dict[str, Tuple[str, datetime]]] = {}
        self._cache_ttl = timedelta(minutes=settings.session_timeout_minutes)

    def is_valid_reference(self, reference: str) -> bool:
        """
        Check if a string is a valid Bitwarden reference notation.
        
        Args:
            reference: String to validate
            
        Returns:
            True if valid reference notation, False otherwise
        """
        return bool(self.REFERENCE_PATTERN.match(reference))

    def parse_reference(self, reference: str) -> Tuple[str, str]:
        """
        Parse Bitwarden reference notation to extract item_id and field.
        
        Args:
            reference: Bitwarden reference string (e.g., "{{ bw:abc123:password }}")
            
        Returns:
            Tuple of (item_id, field)
            
        Raises:
            ValueError: If reference format is invalid
        """
        match = self.REFERENCE_PATTERN.match(reference)
        if not match:
            raise ValueError(f"Invalid Bitwarden reference format: {reference}")
        
        item_id = match.group(1).strip()
        field = match.group(2).strip()
        
        return item_id, field

    async def get_from_cache(
        self, 
        key: str, 
        session_id: str
    ) -> Optional[str]:
        """
        Retrieve a secret from the memory cache.
        
        Args:
            key: Cache key (typically "item_id:field")
            session_id: Session identifier
            
        Returns:
            Cached secret value if found and not expired, None otherwise
        """
        if session_id not in self._cache:
            return None
        
        session_cache = self._cache[session_id]
        if key not in session_cache:
            return None
        
        value, expiry = session_cache[key]
        
        # Check if cache entry has expired
        if datetime.now() >= expiry:
            del session_cache[key]
            return None
        
        return value

    async def set_cache(
        self, 
        key: str, 
        value: str, 
        session_id: str
    ) -> None:
        """
        Store a secret in the memory cache.
        
        Args:
            key: Cache key (typically "item_id:field")
            value: Secret value to cache
            session_id: Session identifier
        """
        if session_id not in self._cache:
            self._cache[session_id] = {}
        
        expiry = datetime.now() + self._cache_ttl
        self._cache[session_id][key] = (value, expiry)

    def clear_session_cache(self, session_id: str) -> None:
        """
        Clear all cached secrets for a specific session.
        
        Args:
            session_id: Session identifier
        """
        if session_id in self._cache:
            del self._cache[session_id]

    async def _fetch_from_bitwarden(
        self, 
        item_id: str, 
        field: str, 
        bw_session_key: str
    ) -> str:
        """
        Fetch a secret value from Bitwarden Vault using the CLI.
        
        Args:
            item_id: Bitwarden item ID
            field: Field name to retrieve
            bw_session_key: Bitwarden session key for authentication
            
        Returns:
            Secret value from Bitwarden
            
        Raises:
            RuntimeError: If Bitwarden CLI command fails
        """
        try:
            # Run Bitwarden CLI command to get item
            cmd = [
                settings.bitwarden_cli_path,
                "get",
                "item",
                item_id,
                "--session",
                bw_session_key
            ]
            
            # Execute command asynchronously
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                raise RuntimeError(
                    f"Failed to fetch item from Bitwarden: {error_msg}"
                )
            
            # Parse JSON response
            item_data = json.loads(stdout.decode())
            
            # Extract field value based on field name
            value = self._extract_field_value(item_data, field)
            
            if value is None:
                raise RuntimeError(
                    f"Field '{field}' not found in Bitwarden item '{item_id}'"
                )
            
            return value
            
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON response from Bitwarden CLI: {e}")
        except Exception as e:
            raise RuntimeError(f"Error fetching from Bitwarden: {e}")

    def _extract_field_value(self, item_data: Dict[str, Any], field: str) -> Optional[str]:
        """
        Extract a field value from Bitwarden item data.
        
        Args:
            item_data: Parsed JSON data from Bitwarden CLI
            field: Field name to extract
            
        Returns:
            Field value if found, None otherwise
        """
        # Common field mappings
        if field == "password":
            return item_data.get("login", {}).get("password")
        elif field == "username":
            return item_data.get("login", {}).get("username")
        elif field == "totp":
            return item_data.get("login", {}).get("totp")
        elif field == "notes":
            return item_data.get("notes")
        
        # Check custom fields
        fields = item_data.get("fields", [])
        for f in fields:
            if f.get("name") == field:
                return f.get("value")
        
        return None

    async def resolve_reference(
        self, 
        reference: str, 
        session_id: str,
        bw_session_key: str
    ) -> str:
        """
        Resolve a Bitwarden reference to its actual secret value.
        
        This method:
        1. Parses the reference notation
        2. Checks the cache
        3. Fetches from Bitwarden if not cached
        4. Caches the result
        
        Args:
            reference: Bitwarden reference string (e.g., "{{ bw:abc123:password }}")
            session_id: Session identifier for caching
            bw_session_key: Bitwarden session key for authentication
            
        Returns:
            Resolved secret value
            
        Raises:
            ValueError: If reference format is invalid
            RuntimeError: If secret cannot be fetched from Bitwarden
        """
        # Parse reference
        item_id, field = self.parse_reference(reference)
        
        # Create cache key
        cache_key = f"{item_id}:{field}"
        
        # Check cache first
        cached_value = await self.get_from_cache(cache_key, session_id)
        if cached_value is not None:
            return cached_value
        
        # Fetch from Bitwarden
        value = await self._fetch_from_bitwarden(item_id, field, bw_session_key)
        
        # Cache the value
        await self.set_cache(cache_key, value, session_id)
        
        return value

    async def resolve_all(
        self, 
        config: Dict[str, Any], 
        session_id: str,
        bw_session_key: str
    ) -> Dict[str, Any]:
        """
        Recursively resolve all Bitwarden references in a configuration dictionary.
        
        Args:
            config: Configuration dictionary that may contain Bitwarden references
            session_id: Session identifier for caching
            bw_session_key: Bitwarden session key for authentication
            
        Returns:
            Configuration dictionary with all references resolved
            
        Raises:
            RuntimeError: If any reference cannot be resolved
        """
        resolved_config = {}
        
        for key, value in config.items():
            if isinstance(value, str) and self.is_valid_reference(value):
                # Resolve the reference
                resolved_config[key] = await self.resolve_reference(
                    value, 
                    session_id, 
                    bw_session_key
                )
            elif isinstance(value, dict):
                # Recursively resolve nested dictionaries
                resolved_config[key] = await self.resolve_all(
                    value, 
                    session_id, 
                    bw_session_key
                )
            elif isinstance(value, list):
                # Resolve references in lists
                resolved_list = []
                for item in value:
                    if isinstance(item, str) and self.is_valid_reference(item):
                        resolved_list.append(
                            await self.resolve_reference(
                                item, 
                                session_id, 
                                bw_session_key
                            )
                        )
                    elif isinstance(item, dict):
                        resolved_list.append(
                            await self.resolve_all(
                                item, 
                                session_id, 
                                bw_session_key
                            )
                        )
                    else:
                        resolved_list.append(item)
                resolved_config[key] = resolved_list
            else:
                # Keep non-reference values as-is
                resolved_config[key] = value
        
        return resolved_config
