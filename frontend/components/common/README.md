# Common UI Components

This directory contains reusable UI components for the Docker MCP Gateway Console.

## Components

### Toast

Toast notification component for displaying temporary messages.

**Features:**
- Auto-dismisses after specified duration (default 3 seconds)
- Supports multiple types: success, error, warning, info
- Accessible with ARIA attributes
- Smooth slide-in animation

**Usage:**

```tsx
import { Toast } from '@/components/common';

<Toast
  message="操作が成功しました"
  type="success"
  duration={3000}
  onClose={() => console.log('Toast closed')}
/>
```

**With ToastContext:**

```tsx
import { useToast } from '@/contexts/ToastContext';

function MyComponent() {
  const { showSuccess, showError, showWarning, showInfo } = useToast();

  const handleSuccess = () => {
    showSuccess('操作が成功しました');
  };

  const handleError = () => {
    showError('エラーが発生しました');
  };

  return (
    <button onClick={handleSuccess}>成功</button>
  );
}
```

### LoadingIndicator

Loading indicator component for displaying progress.

**Features:**
- Three sizes: small, medium, large
- Optional message display
- Can be used inline or as full-screen overlay
- Accessible with ARIA attributes

**Usage:**

```tsx
import { LoadingIndicator } from '@/components/common';

// Inline usage
<LoadingIndicator size="medium" message="読み込み中..." />

// Full-screen overlay
<LoadingIndicator size="large" message="処理中..." fullScreen />
```

### ConfirmDialog

Confirmation dialog component for user actions.

**Features:**
- Modal dialog with backdrop
- Customizable confirm/cancel buttons
- Three types: danger, warning, info
- Accessible with ARIA attributes
- Click outside to cancel

**Usage:**

```tsx
import { ConfirmDialog } from '@/components/common';
import { useState } from 'react';

function MyComponent() {
  const [showDialog, setShowDialog] = useState(false);

  const handleDelete = () => {
    setShowDialog(true);
  };

  const handleConfirm = () => {
    // Perform delete action
    console.log('Confirmed');
    setShowDialog(false);
  };

  const handleCancel = () => {
    setShowDialog(false);
  };

  return (
    <>
      <button onClick={handleDelete}>削除</button>
      {showDialog && (
        <ConfirmDialog
          title="削除の確認"
          message="本当に削除しますか？この操作は取り消せません。"
          confirmText="削除"
          cancelText="キャンセル"
          type="danger"
          onConfirm={handleConfirm}
          onCancel={handleCancel}
        />
      )}
    </>
  );
}
```

## ToastContext

Global toast notification management.

**Setup:**

Wrap your app with `ToastProvider`:

```tsx
import { ToastProvider } from '@/contexts/ToastContext';

export default function RootLayout({ children }) {
  return (
    <html>
      <body>
        <ToastProvider>
          {children}
        </ToastProvider>
      </body>
    </html>
  );
}
```

**API:**

- `showToast(message, type, duration?)` - Show a toast with custom type
- `showSuccess(message, duration?)` - Show success toast (default 3s)
- `showError(message, duration?)` - Show error toast (default 5s)
- `showWarning(message, duration?)` - Show warning toast (default 4s)
- `showInfo(message, duration?)` - Show info toast (default 3s)

## Requirements Validation

These components satisfy the following requirements:

- **要件 10.1**: エラーメッセージの表示 - Toast component with error type
- **要件 10.2**: エラーメッセージの内容 - Toast accepts detailed messages
- **要件 10.4**: 成功メッセージ表示 - Toast component with success type (3 second default)

## Accessibility

All components follow accessibility best practices:
- Proper ARIA attributes (role, aria-label, aria-live, etc.)
- Keyboard navigation support
- Screen reader friendly
- Focus management
