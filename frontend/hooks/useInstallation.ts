'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { installContainer } from '@/lib/api/containers';
import {
  ContainerInstallPayload,
  ContainerInstallResponse,
  InstallationError,
} from '@/lib/types/containers';

interface UseInstallationOptions {
  onSuccess?: (response: ContainerInstallResponse) => void;
  onError?: (error: InstallationError) => void;
}

const DEFAULT_ERROR_MESSAGE = 'インストールに失敗しました';

const normalizeInstallationError = (error: unknown): InstallationError => {
  if (error && typeof error === 'object') {
    const typedError = error as Partial<InstallationError> & { message?: string };
    if (typedError.message || typedError.detail || typedError.status) {
      return {
        message: typedError.message ?? DEFAULT_ERROR_MESSAGE,
        status: typedError.status,
        detail: typedError.detail,
        data: typedError.data,
      };
    }
  }

  if (error instanceof Error) {
    return { message: error.message };
  }

  return { message: DEFAULT_ERROR_MESSAGE };
};

/**
 * インストールAPI呼び出し専用のフック。
 * - パラメータなし、またはonSuccess/onErrorを含むoptionsを渡す
 * - install(payload)でPOST `/api/containers/install` を実行
 * - isLoadingでスピナー状態を制御し、errorに標準化済みエラーを格納
 */
export function useInstallation(options?: UseInstallationOptions) {
  const callbacksRef = useRef(options);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<InstallationError | null>(null);

  useEffect(() => {
    callbacksRef.current = options;
  }, [options]);

  const install = useCallback(async (payload: ContainerInstallPayload) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await installContainer(payload);
      callbacksRef.current?.onSuccess?.(response);
      return response;
    } catch (err) {
      const normalized = normalizeInstallationError(err);
      setError(normalized);
      callbacksRef.current?.onError?.(normalized);
      throw normalized;
    } finally {
      setIsLoading(false);
    }
  }, []);

  return { install, isLoading, error };
}
