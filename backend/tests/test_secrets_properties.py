"""Property-based tests for Secret Manager service.

This module contains property-based tests using Hypothesis to verify
correctness properties of the Secret Manager across a wide range of inputs.
"""

import pytest
from hypothesis import given, strategies as st, settings

from app.services.secrets import SecretManager


# Custom strategies for generating valid Bitwarden reference components
@st.composite
def item_id_strategy(draw):
    """
    Generate valid Bitwarden item IDs.
    
    Item IDs can contain alphanumeric characters, hyphens, and underscores.
    They must be at least 1 character long.
    """
    # Generate a string with valid characters for item IDs
    # Using alphanumeric + hyphens + underscores
    charset = st.text(
        alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'),  # Uppercase, lowercase, digits
            whitelist_characters='-_'
        ),
        min_size=1,
        max_size=50
    )
    return draw(charset)


@st.composite
def field_name_strategy(draw):
    """
    Generate valid Bitwarden field names.
    
    Field names can contain alphanumeric characters, hyphens, and underscores.
    Common field names include: password, username, api_key, secret_token, etc.
    """
    # Generate a string with valid characters for field names
    charset = st.text(
        alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'),  # Uppercase, lowercase, digits
            whitelist_characters='-_'
        ),
        min_size=1,
        max_size=50
    )
    return draw(charset)


@st.composite
def bitwarden_reference_strategy(draw):
    """
    Generate valid Bitwarden reference notation strings.
    
    Format: {{ bw:item-id:field }}
    
    This strategy generates references with varying amounts of whitespace
    to test the parser's robustness.
    """
    item_id = draw(item_id_strategy())
    field = draw(field_name_strategy())
    
    # Generate optional whitespace
    ws_before_bw = draw(st.text(alphabet=' \t', max_size=3))
    ws_after_colon1 = draw(st.text(alphabet=' \t', max_size=3))
    ws_after_colon2 = draw(st.text(alphabet=' \t', max_size=3))
    ws_before_close = draw(st.text(alphabet=' \t', max_size=3))
    
    # Construct the reference with optional whitespace
    reference = f"{{{{{ws_before_bw}bw:{ws_after_colon1}{item_id}:{ws_after_colon2}{field}{ws_before_close}}}}}"
    
    return reference, item_id.strip(), field.strip()


class TestSecretManagerProperties:
    """Property-based tests for SecretManager."""

    @settings(max_examples=100)
    @given(bitwarden_reference_strategy())
    def test_property_5_bitwarden_reference_acceptance(
        self, 
        reference_data
    ):
        """
        **Feature: docker-mcp-gateway-console, Property 5: Bitwarden参照記法の受け入れ**
        
        For any valid Bitwarden reference notation ({{ bw:item-id:field }} format),
        the system should accept it as valid input and be able to parse it back
        to the original components.
        
        This property verifies:
        1. The system accepts the reference as valid (is_valid_reference returns True)
        2. The system can parse the reference without errors
        3. The parsed components match the original item_id and field
        
        **Validates: Requirements 2.1, 2.5, 5.3**
        """
        secret_manager = SecretManager()
        reference, expected_item_id, expected_field = reference_data
        
        # Property 1: System should accept the reference as valid
        assert secret_manager.is_valid_reference(reference), (
            f"System should accept valid Bitwarden reference: {reference}"
        )
        
        # Property 2: System should be able to parse the reference without errors
        try:
            parsed_item_id, parsed_field = secret_manager.parse_reference(reference)
        except Exception as e:
            pytest.fail(
                f"System should parse valid reference without errors. "
                f"Reference: {reference}, Error: {e}"
            )
        
        # Property 3: Parsed components should match the original values
        assert parsed_item_id == expected_item_id, (
            f"Parsed item_id should match original. "
            f"Expected: {expected_item_id}, Got: {parsed_item_id}"
        )
        assert parsed_field == expected_field, (
            f"Parsed field should match original. "
            f"Expected: {expected_field}, Got: {parsed_field}"
        )

    @settings(max_examples=100)
    @given(
        item_id=item_id_strategy(),
        field=field_name_strategy()
    )
    def test_property_5_reference_roundtrip(
        self,
        item_id,
        field
    ):
        """
        **Feature: docker-mcp-gateway-console, Property 5: Bitwarden参照記法の受け入れ**
        
        For any valid item_id and field, constructing a reference and parsing it
        should return the original values (round-trip property).
        
        This is a complementary test that verifies the reference format is
        consistently handled.
        
        **Validates: Requirements 2.1, 2.5, 5.3**
        """
        secret_manager = SecretManager()
        
        # Construct a reference in the standard format
        reference = f"{{{{ bw:{item_id}:{field} }}}}"
        
        # The reference should be valid
        assert secret_manager.is_valid_reference(reference), (
            f"Constructed reference should be valid: {reference}"
        )
        
        # Parse it back
        parsed_item_id, parsed_field = secret_manager.parse_reference(reference)
        
        # Should get back the original values
        assert parsed_item_id == item_id, (
            f"Round-trip should preserve item_id. "
            f"Original: {item_id}, After round-trip: {parsed_item_id}"
        )
        assert parsed_field == field, (
            f"Round-trip should preserve field. "
            f"Original: {field}, After round-trip: {parsed_field}"
        )

    @settings(max_examples=100)
    @given(
        st.text(
            alphabet=st.characters(blacklist_categories=('Cs',)),  # Exclude surrogates
            min_size=0,
            max_size=100
        ).filter(lambda s: not SecretManager.REFERENCE_PATTERN.match(s))
    )
    def test_property_5_invalid_references_rejected(
        self,
        invalid_text
    ):
        """
        **Feature: docker-mcp-gateway-console, Property 5: Bitwarden参照記法の受け入れ**
        
        For any string that does NOT match the Bitwarden reference format,
        the system should reject it as invalid.
        
        This is the contrapositive of the acceptance property - ensuring
        that only valid references are accepted.
        
        **Validates: Requirements 2.1, 2.5, 5.3**
        """
        secret_manager = SecretManager()
        
        # Invalid text should not be accepted as a valid reference
        assert not secret_manager.is_valid_reference(invalid_text), (
            f"System should reject invalid reference format: {invalid_text}"
        )
        
        # Attempting to parse invalid text should raise ValueError
        if invalid_text:  # Only test non-empty strings for parsing
            with pytest.raises(ValueError):
                secret_manager.parse_reference(invalid_text)


    @settings(max_examples=100)
    @given(
        reference_data=bitwarden_reference_strategy(),
        secret_value=st.text(min_size=1, max_size=100),
        session_id=st.text(
            alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='-'),
            min_size=10,
            max_size=50
        ),
        bw_session_key=st.text(
            alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='-_'),
            min_size=20,
            max_size=100
        )
    )
    @pytest.mark.asyncio
    async def test_property_6_reference_resolution(
        self,
        reference_data,
        secret_value,
        session_id,
        bw_session_key
    ):
        """
        **Feature: docker-mcp-gateway-console, Property 6: 参照記法の解決**
        
        For any Bitwarden reference notation in environment variables,
        when a container starts, the system should fetch the corresponding
        value from Bitwarden Vault and inject it into the environment variable.
        
        This property verifies:
        1. The system can resolve a reference to its actual secret value
        2. The resolved value matches what Bitwarden returns
        3. The value is cached for subsequent requests
        4. Cached values are returned without re-fetching from Bitwarden
        
        **Validates: Requirements 2.2**
        """
        from unittest.mock import AsyncMock, patch
        import json
        
        secret_manager = SecretManager()
        reference, item_id, field = reference_data
        
        # Create mock Bitwarden item data
        mock_item_data = {
            "id": item_id,
            "login": {
                "password": secret_value if field == "password" else "other-password",
                "username": secret_value if field == "username" else "other-username",
            },
            "fields": [
                {"name": field, "value": secret_value}
            ],
            "notes": secret_value if field == "notes" else "other-notes"
        }
        
        # Mock the Bitwarden CLI subprocess
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(
            return_value=(json.dumps(mock_item_data).encode(), b"")
        )
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            # First resolution: should fetch from Bitwarden
            resolved_value = await secret_manager.resolve_reference(
                reference,
                session_id,
                bw_session_key
            )
            
            # Property 1: Resolved value should match the secret value from Bitwarden
            assert resolved_value == secret_value, (
                f"Resolved value should match Bitwarden response. "
                f"Expected: {secret_value}, Got: {resolved_value}"
            )
            
            # Verify that Bitwarden CLI was called
            assert mock_process.communicate.call_count == 1, (
                "Bitwarden CLI should be called once for first resolution"
            )
            
            # Reset mock call count
            mock_process.communicate.reset_mock()
            
            # Second resolution: should use cache (no Bitwarden call)
            cached_value = await secret_manager.resolve_reference(
                reference,
                session_id,
                bw_session_key
            )
            
            # Property 2: Cached value should match the original resolved value
            assert cached_value == secret_value, (
                f"Cached value should match original resolution. "
                f"Expected: {secret_value}, Got: {cached_value}"
            )
            
            # Property 3: Bitwarden should NOT be called again (cache hit)
            assert mock_process.communicate.call_count == 0, (
                "Bitwarden CLI should not be called for cached values"
            )
            
            # Verify cache contains the value
            cache_key = f"{item_id}:{field}"
            cached_from_cache = await secret_manager.get_from_cache(
                cache_key,
                session_id
            )
            
            # Property 4: Cache should contain the resolved value
            assert cached_from_cache == secret_value, (
                f"Cache should contain the resolved value. "
                f"Expected: {secret_value}, Got: {cached_from_cache}"
            )


    @settings(max_examples=100)
    @given(
        reference_data=bitwarden_reference_strategy(),
        session_id=st.text(
            alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='-'),
            min_size=10,
            max_size=50
        ),
        bw_session_key=st.text(
            alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='-_'),
            min_size=20,
            max_size=100
        ),
        error_type=st.sampled_from(['nonexistent_item', 'nonexistent_field', 'cli_error'])
    )
    @pytest.mark.asyncio
    async def test_property_7_invalid_reference_error_handling(
        self,
        reference_data,
        session_id,
        bw_session_key,
        error_type
    ):
        """
        **Feature: docker-mcp-gateway-console, Property 7: 無効な参照のエラーハンドリング**
        
        For any invalid Bitwarden reference (non-existent item ID or field),
        the system should abort container startup and return an error message.
        
        This property verifies:
        1. When Bitwarden returns an error (item not found), resolve_reference raises RuntimeError
        2. When a field doesn't exist in the item, resolve_reference raises RuntimeError
        3. When Bitwarden CLI fails, resolve_reference raises RuntimeError
        4. The error message is descriptive and helps identify the problem
        
        **Validates: Requirements 2.3**
        """
        from unittest.mock import AsyncMock, patch
        import json
        
        secret_manager = SecretManager()
        reference, item_id, field = reference_data
        
        # Create different error scenarios based on error_type
        if error_type == 'nonexistent_item':
            # Mock Bitwarden CLI returning error for non-existent item
            mock_process = AsyncMock()
            mock_process.returncode = 1
            mock_process.communicate = AsyncMock(
                return_value=(b"", b"Not found.")
            )
        elif error_type == 'nonexistent_field':
            # Mock Bitwarden returning valid item but without the requested field
            mock_item_data = {
                "id": item_id,
                "login": {
                    "password": "some-password",
                    "username": "some-username",
                },
                "fields": [
                    {"name": "other_field", "value": "other-value"}
                ],
                "notes": "some-notes"
            }
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(
                return_value=(json.dumps(mock_item_data).encode(), b"")
            )
        else:  # cli_error
            # Mock Bitwarden CLI command failure
            mock_process = AsyncMock()
            mock_process.returncode = 1
            mock_process.communicate = AsyncMock(
                return_value=(b"", b"Bitwarden CLI error: authentication failed")
            )
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            # Property 1: System should raise RuntimeError for invalid references
            with pytest.raises(RuntimeError) as exc_info:
                await secret_manager.resolve_reference(
                    reference,
                    session_id,
                    bw_session_key
                )
            
            # Property 2: Error message should be descriptive
            error_message = str(exc_info.value)
            assert len(error_message) > 0, (
                "Error message should not be empty"
            )
            
            # Property 3: Error message should contain relevant context
            if error_type == 'nonexistent_item':
                assert "Failed to fetch item from Bitwarden" in error_message or "Not found" in error_message, (
                    f"Error message should indicate item fetch failure. Got: {error_message}"
                )
            elif error_type == 'nonexistent_field':
                assert "not found" in error_message.lower() and field in error_message, (
                    f"Error message should indicate field not found. Got: {error_message}"
                )
            elif error_type == 'cli_error':
                assert "Failed to fetch item from Bitwarden" in error_message or "authentication failed" in error_message, (
                    f"Error message should indicate CLI error. Got: {error_message}"
                )
            
            # Property 4: Cache should not contain the failed value
            cache_key = f"{item_id}:{field}"
            cached_value = await secret_manager.get_from_cache(
                cache_key,
                session_id
            )
            assert cached_value is None, (
                "Failed resolution should not cache any value"
            )


    @settings(max_examples=100)
    @given(
        reference_data=bitwarden_reference_strategy(),
        secret_value=st.text(min_size=1, max_size=100),
        session_id=st.text(
            alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='-'),
            min_size=10,
            max_size=50
        ),
        bw_session_key=st.text(
            alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='-_'),
            min_size=20,
            max_size=100
        )
    )
    @pytest.mark.asyncio
    async def test_property_8_no_disk_writes(
        self,
        reference_data,
        secret_value,
        session_id,
        bw_session_key
    ):
        """
        **Feature: docker-mcp-gateway-console, Property 8: 機密情報のディスク書き込み禁止**
        
        For any secret retrieved from Bitwarden Vault, the system should never
        write that value to disk (log files, config files, etc.).
        
        This property verifies:
        1. Secrets are only stored in memory (in the cache)
        2. No file I/O operations are performed with secret values
        3. The cache is in-memory only (not persisted to disk)
        4. Secret values are not written to any files during resolution
        
        **Validates: Requirements 2.4, 7.3**
        """
        from unittest.mock import AsyncMock, patch, mock_open, MagicMock
        import json
        import builtins
        
        secret_manager = SecretManager()
        reference, item_id, field = reference_data
        
        # Create mock Bitwarden item data
        mock_item_data = {
            "id": item_id,
            "login": {
                "password": secret_value if field == "password" else "other-password",
                "username": secret_value if field == "username" else "other-username",
            },
            "fields": [
                {"name": field, "value": secret_value}
            ],
            "notes": secret_value if field == "notes" else "other-notes"
        }
        
        # Mock the Bitwarden CLI subprocess
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(
            return_value=(json.dumps(mock_item_data).encode(), b"")
        )
        
        # Track all file operations
        file_operations = []
        original_open = builtins.open
        
        def tracked_open(*args, **kwargs):
            """Track all file open operations."""
            # Record the operation
            file_operations.append({
                'operation': 'open',
                'args': args,
                'kwargs': kwargs,
                'mode': kwargs.get('mode', args[1] if len(args) > 1 else 'r')
            })
            # Call original open
            return original_open(*args, **kwargs)
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            with patch('builtins.open', side_effect=tracked_open):
                # Resolve the reference
                resolved_value = await secret_manager.resolve_reference(
                    reference,
                    session_id,
                    bw_session_key
                )
                
                # Property 1: Resolved value should match the secret
                assert resolved_value == secret_value, (
                    f"Resolved value should match secret. "
                    f"Expected: {secret_value}, Got: {resolved_value}"
                )
                
                # Property 2: No file write operations should have occurred
                write_operations = [
                    op for op in file_operations 
                    if 'w' in op['mode'] or 'a' in op['mode'] or '+' in op['mode']
                ]
                
                assert len(write_operations) == 0, (
                    f"No file write operations should occur during secret resolution. "
                    f"Found {len(write_operations)} write operations: {write_operations}"
                )
                
                # Property 3: Secret should only exist in memory cache
                cache_key = f"{item_id}:{field}"
                cached_value = await secret_manager.get_from_cache(
                    cache_key,
                    session_id
                )
                
                assert cached_value == secret_value, (
                    f"Secret should be cached in memory. "
                    f"Expected: {secret_value}, Got: {cached_value}"
                )
                
                # Property 4: Verify cache is in-memory only (not a file-backed structure)
                # The cache should be a plain Python dict, not a file-backed database
                assert isinstance(secret_manager._cache, dict), (
                    "Cache should be a plain Python dict (in-memory only)"
                )
                
                # Property 5: Verify no persistence mechanism exists
                # Check that the cache doesn't have any file-related attributes
                cache_attrs = dir(secret_manager._cache)
                file_related_attrs = [
                    attr for attr in cache_attrs 
                    if any(keyword in attr.lower() for keyword in ['file', 'disk', 'persist', 'save', 'dump'])
                ]
                
                assert len(file_related_attrs) == 0, (
                    f"Cache should not have file-related attributes. "
                    f"Found: {file_related_attrs}"
                )
                
                # Property 6: Verify the secret value is not in any file operation arguments
                for op in file_operations:
                    # Check if secret value appears in any file operation
                    args_str = str(op['args'])
                    kwargs_str = str(op['kwargs'])
                    
                    assert secret_value not in args_str, (
                        f"Secret value should not appear in file operation arguments. "
                        f"Operation: {op}"
                    )
                    assert secret_value not in kwargs_str, (
                        f"Secret value should not appear in file operation kwargs. "
                        f"Operation: {op}"
                    )


    @settings(max_examples=100)
    @given(
        reference_data=bitwarden_reference_strategy(),
        secret_value=st.text(min_size=1, max_size=100),
        session_id=st.text(
            alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='-'),
            min_size=10,
            max_size=50
        ),
        bw_session_key=st.text(
            alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='-_'),
            min_size=20,
            max_size=100
        )
    )
    @pytest.mark.asyncio
    async def test_property_23_secret_caching(
        self,
        reference_data,
        secret_value,
        session_id,
        bw_session_key
    ):
        """
        **Feature: docker-mcp-gateway-console, Property 23: Secretのキャッシング**
        
        For any secret, when the same secret is requested twice during a session,
        the second request should return the cached value without accessing
        Bitwarden Vault again.
        
        This property verifies:
        1. First request fetches from Bitwarden and caches the value
        2. Second request returns the same value from cache
        3. Bitwarden is not accessed on the second request (cache hit)
        4. Cache is session-specific (different sessions have separate caches)
        
        **Validates: Requirements 7.1, 7.4**
        """
        from unittest.mock import AsyncMock, patch
        import json
        
        secret_manager = SecretManager()
        reference, item_id, field = reference_data
        
        # Create mock Bitwarden item data
        mock_item_data = {
            "id": item_id,
            "login": {
                "password": secret_value if field == "password" else "other-password",
                "username": secret_value if field == "username" else "other-username",
            },
            "fields": [
                {"name": field, "value": secret_value}
            ],
            "notes": secret_value if field == "notes" else "other-notes"
        }
        
        # Mock the Bitwarden CLI subprocess
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(
            return_value=(json.dumps(mock_item_data).encode(), b"")
        )
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            # Property 1: First request should fetch from Bitwarden
            first_value = await secret_manager.resolve_reference(
                reference,
                session_id,
                bw_session_key
            )
            
            assert first_value == secret_value, (
                f"First resolution should return the secret value. "
                f"Expected: {secret_value}, Got: {first_value}"
            )
            
            # Verify Bitwarden CLI was called exactly once
            assert mock_process.communicate.call_count == 1, (
                "Bitwarden CLI should be called once for first resolution"
            )
            
            # Reset mock to track subsequent calls
            initial_call_count = mock_process.communicate.call_count
            mock_process.communicate.reset_mock()
            
            # Property 2: Second request should use cache (no Bitwarden access)
            second_value = await secret_manager.resolve_reference(
                reference,
                session_id,
                bw_session_key
            )
            
            assert second_value == secret_value, (
                f"Second resolution should return the same cached value. "
                f"Expected: {secret_value}, Got: {second_value}"
            )
            
            # Property 3: Bitwarden should NOT be called again (cache hit)
            assert mock_process.communicate.call_count == 0, (
                f"Bitwarden CLI should not be called for cached values. "
                f"Expected 0 calls, got {mock_process.communicate.call_count}"
            )
            
            # Property 4: Cache should contain the value
            cache_key = f"{item_id}:{field}"
            cached_value = await secret_manager.get_from_cache(
                cache_key,
                session_id
            )
            
            assert cached_value == secret_value, (
                f"Cache should contain the resolved value. "
                f"Expected: {secret_value}, Got: {cached_value}"
            )
            
            # Property 5: Multiple subsequent requests should all use cache
            # Make 3 more requests to verify consistent caching behavior
            for i in range(3):
                nth_value = await secret_manager.resolve_reference(
                    reference,
                    session_id,
                    bw_session_key
                )
                
                assert nth_value == secret_value, (
                    f"Request {i+3} should return cached value. "
                    f"Expected: {secret_value}, Got: {nth_value}"
                )
            
            # Verify still no additional Bitwarden calls
            assert mock_process.communicate.call_count == 0, (
                f"Bitwarden CLI should not be called for any cached requests. "
                f"Expected 0 calls, got {mock_process.communicate.call_count}"
            )
            
            # Property 6: Different sessions should have separate caches
            different_session_id = session_id + "-different"
            
            # Reset mock for new session test
            mock_process.communicate.reset_mock()
            
            # Request with different session should fetch from Bitwarden again
            different_session_value = await secret_manager.resolve_reference(
                reference,
                different_session_id,
                bw_session_key
            )
            
            assert different_session_value == secret_value, (
                f"Different session should get the same secret value. "
                f"Expected: {secret_value}, Got: {different_session_value}"
            )
            
            # Property 7: Different session should trigger Bitwarden access
            assert mock_process.communicate.call_count == 1, (
                f"Different session should fetch from Bitwarden. "
                f"Expected 1 call, got {mock_process.communicate.call_count}"
            )
            
            # Property 8: Both sessions should have their own cached values
            original_session_cache = await secret_manager.get_from_cache(
                cache_key,
                session_id
            )
            different_session_cache = await secret_manager.get_from_cache(
                cache_key,
                different_session_id
            )
            
            assert original_session_cache == secret_value, (
                "Original session cache should still contain the value"
            )
            assert different_session_cache == secret_value, (
                "Different session cache should contain the value"
            )


    @settings(max_examples=100)
    @given(
        reference_data=bitwarden_reference_strategy(),
        secret_value=st.text(min_size=1, max_size=100),
        session_id=st.text(
            alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='-'),
            min_size=10,
            max_size=50
        ),
        bw_session_key=st.text(
            alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='-_'),
            min_size=20,
            max_size=100
        )
    )
    @pytest.mark.asyncio
    async def test_property_25_cache_expiration(
        self,
        reference_data,
        secret_value,
        session_id,
        bw_session_key
    ):
        """
        **Feature: docker-mcp-gateway-console, Property 25: キャッシュ有効期限**
        
        For any cached secret, when the cache TTL expires, the next request
        should re-fetch the value from Bitwarden Vault instead of using the
        expired cache entry.
        
        This property verifies:
        1. Secrets are cached with an expiration time
        2. Before expiration, cached values are returned
        3. After expiration, cache returns None (expired)
        4. After expiration, resolve_reference fetches from Bitwarden again
        5. The newly fetched value is cached with a new expiration time
        
        **Validates: Requirements 7.5**
        """
        from unittest.mock import AsyncMock, patch
        from datetime import datetime, timedelta
        import json
        
        secret_manager = SecretManager()
        reference, item_id, field = reference_data
        
        # Create mock Bitwarden item data
        mock_item_data = {
            "id": item_id,
            "login": {
                "password": secret_value if field == "password" else "other-password",
                "username": secret_value if field == "username" else "other-username",
            },
            "fields": [
                {"name": field, "value": secret_value}
            ],
            "notes": secret_value if field == "notes" else "other-notes"
        }
        
        # Mock the Bitwarden CLI subprocess
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(
            return_value=(json.dumps(mock_item_data).encode(), b"")
        )
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            # Property 1: First resolution should fetch from Bitwarden and cache
            first_value = await secret_manager.resolve_reference(
                reference,
                session_id,
                bw_session_key
            )
            
            assert first_value == secret_value, (
                f"First resolution should return the secret value. "
                f"Expected: {secret_value}, Got: {first_value}"
            )
            
            # Verify Bitwarden CLI was called once
            assert mock_process.communicate.call_count == 1, (
                "Bitwarden CLI should be called once for first resolution"
            )
            
            # Property 2: Verify the value is cached with an expiration time
            cache_key = f"{item_id}:{field}"
            
            # Access internal cache to verify structure
            assert session_id in secret_manager._cache, (
                "Session should exist in cache"
            )
            assert cache_key in secret_manager._cache[session_id], (
                "Cache key should exist in session cache"
            )
            
            cached_entry = secret_manager._cache[session_id][cache_key]
            assert isinstance(cached_entry, tuple), (
                "Cache entry should be a tuple"
            )
            assert len(cached_entry) == 2, (
                "Cache entry should contain (value, expiry)"
            )
            
            cached_value, expiry_time = cached_entry
            assert cached_value == secret_value, (
                f"Cached value should match secret. Expected: {secret_value}, Got: {cached_value}"
            )
            assert isinstance(expiry_time, datetime), (
                "Expiry time should be a datetime object"
            )
            assert expiry_time > datetime.now(), (
                "Expiry time should be in the future"
            )
            
            # Property 3: Before expiration, cache should return the value
            cached_before_expiry = await secret_manager.get_from_cache(
                cache_key,
                session_id
            )
            
            assert cached_before_expiry == secret_value, (
                f"Cache should return value before expiration. "
                f"Expected: {secret_value}, Got: {cached_before_expiry}"
            )
            
            # Reset mock to track subsequent calls
            mock_process.communicate.reset_mock()
            
            # Property 4: Simulate cache expiration by setting expiry to the past
            # Directly manipulate the cache to set an expired time
            past_expiry = datetime.now() - timedelta(seconds=1)
            secret_manager._cache[session_id][cache_key] = (secret_value, past_expiry)
            
            # Property 5: After expiration, get_from_cache should return None
            cached_after_expiry = await secret_manager.get_from_cache(
                cache_key,
                session_id
            )
            
            assert cached_after_expiry is None, (
                "Cache should return None for expired entries"
            )
            
            # Property 6: After expiration, the expired entry should be removed from cache
            assert cache_key not in secret_manager._cache[session_id], (
                "Expired cache entry should be removed from cache"
            )
            
            # Property 7: After expiration, resolve_reference should fetch from Bitwarden again
            refetched_value = await secret_manager.resolve_reference(
                reference,
                session_id,
                bw_session_key
            )
            
            assert refetched_value == secret_value, (
                f"Re-fetched value should match secret. "
                f"Expected: {secret_value}, Got: {refetched_value}"
            )
            
            # Property 8: Bitwarden should be called again after cache expiration
            assert mock_process.communicate.call_count == 1, (
                f"Bitwarden CLI should be called again after cache expiration. "
                f"Expected 1 call, got {mock_process.communicate.call_count}"
            )
            
            # Property 9: The newly fetched value should be cached with a new expiration
            assert cache_key in secret_manager._cache[session_id], (
                "Re-fetched value should be cached again"
            )
            
            new_cached_entry = secret_manager._cache[session_id][cache_key]
            new_cached_value, new_expiry_time = new_cached_entry
            
            assert new_cached_value == secret_value, (
                f"Newly cached value should match secret. "
                f"Expected: {secret_value}, Got: {new_cached_value}"
            )
            assert new_expiry_time > datetime.now(), (
                "New expiry time should be in the future"
            )
            
            # Property 10: The new expiry time should be different from the old one
            assert new_expiry_time != past_expiry, (
                "New expiry time should be different from the expired one"
            )
            
            # Property 11: Verify the cache TTL is applied correctly
            # The new expiry should be approximately cache_ttl from now
            expected_expiry = datetime.now() + secret_manager._cache_ttl
            time_difference = abs((new_expiry_time - expected_expiry).total_seconds())
            
            # Allow 2 seconds tolerance for test execution time
            assert time_difference < 2, (
                f"New expiry time should be approximately cache_ttl from now. "
                f"Expected: {expected_expiry}, Got: {new_expiry_time}, "
                f"Difference: {time_difference} seconds"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
