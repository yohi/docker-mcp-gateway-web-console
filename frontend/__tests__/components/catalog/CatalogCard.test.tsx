import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import CatalogCard from '../../../components/catalog/CatalogCard';

// Mock useContainers
const mockUseContainers = jest.fn();
jest.mock('../../../hooks/useContainers', () => ({
    useContainers: () => mockUseContainers(),
}));

describe('CatalogCard', () => {
    const mockItem = {
        id: 'test-id',
        name: 'Test Server',
        description: 'Test Description',
        category: 'utilities',
        docker_image: 'test/image:latest',
        default_env: {},
        required_envs: [],
        required_secrets: [],
        vendor: 'test-vendor',
        icon_url: '',
        required_scopes: ['repo:read'],
        verify_signatures: true,
    };

    const mockMutate = jest.fn();

    beforeEach(() => {
        mockUseContainers.mockReturnValue({
            containers: [],
            isLoading: false,
            isError: false,
            error: undefined,
            refresh: mockMutate,
        });
    });

    it('renders item details', () => {
        mockUseContainers.mockReturnValue({
            containers: [],
            isLoading: false,
        });

        render(<CatalogCard item={mockItem} onInstall={jest.fn()} />);

        expect(screen.getByText('Test Server')).toBeInTheDocument();
        expect(screen.getByText('Test Description')).toBeInTheDocument();
        expect(screen.getByText('utilities')).toBeInTheDocument();
        expect(screen.getByText('test/image:latest')).toBeInTheDocument();
    });

    it('shows install button when not installed', () => {
        const onInstall = jest.fn();
        render(<CatalogCard item={mockItem} onInstall={onInstall} />);

        const button = screen.getByRole('button', { name: 'インストール' });
        expect(button).toBeInTheDocument();

        fireEvent.click(button);
        expect(onInstall).toHaveBeenCalledWith(mockItem);
    });

    it('shows existing status when container is running', () => {
        mockUseContainers.mockReturnValue({
            containers: [{
                id: 'c1',
                name: 'test-c',
                image: 'test/image:latest',
                status: 'running',
                created_at: '',
                ports: {},
                labels: {}
            }],
            isLoading: false,
        });

        render(<CatalogCard item={mockItem} onInstall={jest.fn()} />);

        expect(screen.queryByRole('button', { name: 'インストール' })).not.toBeInTheDocument();
        expect(screen.getByText('実行中')).toBeInTheDocument();
    });

    it('shows installed status when container exists but stopped', () => {
        mockUseContainers.mockReturnValue({
            containers: [{
                id: 'c1',
                name: 'test-c',
                image: 'test/image:latest',
                status: 'stopped',
                created_at: '',
                ports: {},
                labels: {}
            }],
            isLoading: false,
        });

        render(<CatalogCard item={mockItem} onInstall={jest.fn()} />);

        expect(screen.getByText('インストール済み')).toBeInTheDocument();
    });

    it('shows loading state', () => {
        mockUseContainers.mockReturnValue({
            containers: [],
            isLoading: true,
        });

        render(<CatalogCard item={mockItem} onInstall={jest.fn()} />);

        // Exact text depends on implementation "Checking..." or similar
        // I'll assume we put a disabled button or text
        expect(screen.getByRole('button')).toBeDisabled();
    });

    it('shows required scopes and signature badge', () => {
        mockUseContainers.mockReturnValue({
            containers: [],
            isLoading: false,
        });

        render(<CatalogCard item={mockItem} onInstall={jest.fn()} />);

        expect(screen.getByText('要求スコープ')).toBeInTheDocument();
        expect(screen.getByText('repo:read')).toBeInTheDocument();
        expect(screen.getByText('署名検証: 有効')).toBeInTheDocument();
    });

    it('calls onSelect when card clicked', () => {
        const onSelect = jest.fn();
        render(<CatalogCard item={mockItem} onInstall={jest.fn()} onSelect={onSelect} />);

        const card = screen.getByTestId('catalog-card');
        card.click();
        expect(onSelect).toHaveBeenCalledWith(mockItem);
    });

    it('renders remote catalog item with remote badge and endpoint', () => {
        const remoteItem = {
            ...mockItem,
            docker_image: '',
            remote_endpoint: 'https://api.example.com/sse',
            is_remote: true,
            server_type: 'remote',
        };
        const onSelect = jest.fn();

        render(<CatalogCard item={remoteItem} onInstall={jest.fn()} onSelect={onSelect} />);

        expect(screen.getByText('リモート')).toBeInTheDocument();
        expect(screen.getByText('https://api.example.com/sse')).toBeInTheDocument();
        expect(screen.queryByText('インストール')).not.toBeInTheDocument();

        screen.getByRole('button', { name: /詳細/ }).click();
        expect(onSelect).toHaveBeenCalledWith(remoteItem);
    });
});
