import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import CatalogPage from '../../app/catalog/page';
import { createContainer } from '../../lib/api/containers';
import { useSession } from '../../contexts/SessionContext';

// Mocks
jest.mock('../../lib/api/catalog', () => ({
    searchCatalog: jest.fn(),
}));
jest.mock('../../lib/api/containers', () => ({
    createContainer: jest.fn(),
}));

// Mock Router
jest.mock('next/navigation', () => ({
    useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
}));

// Mock Session
jest.mock('../../contexts/SessionContext', () => ({
    useSession: jest.fn(),
    SessionProvider: ({ children }: any) => <div>{children}</div>
}));

// Mock Layout
jest.mock('../../components/layout', () => ({
    MainLayout: ({ children }: any) => <div data-testid="main-layout">{children}</div>
}));

// Mock ProtectedRoute
jest.mock('../../components/auth/ProtectedRoute', () => {
    return {
        __esModule: true,
        default: ({ children }: any) => <div data-testid="protected-route">{children}</div>
    };
});

// Mock SWR to return data
jest.mock('swr', () => ({
    __esModule: true,
    default: () => ({
        data: {
            servers: [{
                id: '1',
                name: 'Test Server',
                description: 'Desc',
                category: 'cat',
                docker_image: 'img:fake',
                required_secrets: [],
                default_env: { 'E1': 'V1' }
            }],
            cached: false
        },
        isLoading: false,
        error: undefined,
        mutate: jest.fn()
    }),
}));

// Mock useContainers
jest.mock('../../hooks/useContainers', () => ({
    useContainers: () => ({ containers: [], isLoading: false, refresh: jest.fn() })
}));

// Mock Toast
const mockShowSuccess = jest.fn();
jest.mock('../../contexts/ToastContext', () => ({
    useToast: () => ({ showSuccess: mockShowSuccess, showError: jest.fn() })
}));

describe('Catalog Page Integration', () => {
    beforeEach(() => {
        jest.clearAllMocks();
        (useSession as jest.Mock).mockReturnValue({
            session: { user: 'test' },
            isLoading: false
        });
    });

    it('allows installing a server from catalog', async () => {
        (createContainer as jest.Mock).mockResolvedValue({ container_id: 'cid' });

        render(<CatalogPage />);

        // 1. Check server list
        expect(screen.getByText('Test Server')).toBeInTheDocument();

        // 2. Click Install
        const installBtn = screen.getByRole('button', { name: 'インストール' });
        fireEvent.click(installBtn);

        // 3. Check Modal
        expect(screen.getByText('Test Serverをインストール')).toBeInTheDocument();

        // 4. Click Install in Modal
        const buttons = screen.getAllByRole('button', { name: 'インストール' });
        // The last one is likely the modal one (rendered later).
        const modalInstallBtn = buttons[buttons.length - 1];

        fireEvent.click(modalInstallBtn);

        // 5. Verify call
        await waitFor(() => {
            expect(createContainer).toHaveBeenCalledWith(expect.objectContaining({
                name: 'Test Server',
                image: 'img:fake',
                env: expect.objectContaining({ 'E1': 'V1' })
            }));
        });

        expect(mockShowSuccess).toHaveBeenCalledWith(expect.stringContaining('installed successfully'));
    });
});
