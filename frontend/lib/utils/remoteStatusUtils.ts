import { RemoteServerStatus } from '@/lib/types/remote';

type RemoteStatusInput = RemoteServerStatus | string | null | undefined;

export function getRemoteStatusLabel(status: RemoteStatusInput): string {
  switch (status) {
    case RemoteServerStatus.REGISTERED:
    case 'registered':
      return '登録済み';
    case RemoteServerStatus.AUTH_REQUIRED:
    case 'auth_required':
      return '要認証';
    case RemoteServerStatus.AUTHENTICATED:
    case 'authenticated':
      return '認証済み';
    case RemoteServerStatus.DISABLED:
    case 'disabled':
      return '無効';
    case RemoteServerStatus.ERROR:
    case 'error':
      return 'エラー';
    case RemoteServerStatus.UNREGISTERED:
    case 'unregistered':
    default:
      return '未登録';
  }
}
