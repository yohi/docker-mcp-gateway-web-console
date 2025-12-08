'use client';

import { useState, useEffect } from 'react';

interface SecretReferenceInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  label?: string;
  inputId?: string;
  error?: string;
  onBlur?: () => void;
  required?: boolean;
}

/**
 * Input component that supports Bitwarden reference notation.
 * Format: {{ bw:item-id:field }}
 */
export default function SecretReferenceInput({
  value,
  onChange,
  placeholder = 'Enter value or {{ bw:item-id:field }}',
  label,
  error,
  inputId,
  onBlur,
  required = false,
}: SecretReferenceInputProps) {
  const [isReference, setIsReference] = useState(false);

  useEffect(() => {
    // Check if the value matches Bitwarden reference notation
    const referencePattern = /^\{\{\s*bw:[^:]+:[^}]+\s*\}\}$/;
    setIsReference(referencePattern.test(value));
  }, [value]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange(e.target.value);
  };

  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label className="text-sm font-medium text-gray-700" htmlFor={inputId}>
          {label}
        </label>
      )}
      <div className="relative">
        <input
          type="text"
          id={inputId}
          value={value}
          onChange={handleChange}
          onBlur={onBlur}
          placeholder={placeholder}
          required={required}
          aria-required={required}
          className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 ${
            error
              ? 'border-red-500 focus:ring-red-500'
              : isReference
              ? 'border-blue-500 focus:ring-blue-500 bg-blue-50'
              : 'border-gray-300 focus:ring-blue-500'
          }`}
        />
        {isReference && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2">
            <span className="text-xs text-blue-600 font-medium">
              🔐 Bitwarden
            </span>
          </div>
        )}
      </div>
      {error && (
        <p className="text-xs text-red-600">{error}</p>
      )}
      {isReference && !error && (
        <p className="text-xs text-blue-600">
          This value will be resolved from Bitwarden at runtime
        </p>
      )}
      {!isReference && !error && value && (
        <p className="text-xs text-gray-500">
          Tip: Use {`{{ bw:item-id:field }}`} to reference Bitwarden secrets
        </p>
      )}
    </div>
  );
}
