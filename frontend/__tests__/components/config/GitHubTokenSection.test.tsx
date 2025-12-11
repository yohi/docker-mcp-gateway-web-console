import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import GitHubTokenSection from '@/components/config/GitHubTokenSection';
import { ToastProvider } from '@/contexts/ToastContext';
import {
  deleteGitHubToken,
  fetchGitHubTokenStatus,
  saveGitHubToken,
  searchBitwardenItems,
} from '@/lib/api/githubToken';

jest.mock('@/lib/api/githubToken');

const mockFetchStatus = fetchGitHubTokenStatus as jest.Mock;
const mockSearch = searchBitwardenItems as jest.Mock;
const mockSave = saveGitHubToken as jest.Mock;
const mockDelete = deleteGitHubToken as jest.Mock;

const renderWithToast = () =>
  render(
    <ToastProvider>
      <GitHubTokenSection />
    </ToastProvider>
  );

describe('GitHubTokenSection', () => {
  beforeEach(() => {
    mockFetchStatus.mockResolvedValue({
      configured: false,
      source: null,
      updated_at: null,
      updated_by: null,
    });
    mockSearch.mockResolvedValue([]);
    mockSave.mockResolvedValue({
      success: true,
      status: { configured: true, source: 'bitwarden:item:password', updated_by: 'tester', updated_at: null },
    });
    mockDelete.mockResolvedValue({ success: true });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('loads status on mount', async () => {
    renderWithToast();
    await waitFor(() => expect(mockFetchStatus).toHaveBeenCalled());
  });

  it('searches Bitwarden and saves token', async () => {
    mockSearch.mockResolvedValue([
      { id: 'item1', name: 'Example', fields: ['password'], type: 'login' },
    ]);

    renderWithToast();

    const input = screen.getByPlaceholderText('Bitwardenアイテム名で検索');
    fireEvent.change(input, { target: { value: 'Example' } });
    fireEvent.click(screen.getByText('Bitwardenを検索'));

    await waitFor(() => expect(mockSearch).toHaveBeenCalledWith('Example', 20));

    fireEvent.click(screen.getByText('Bitwardenから設定'));
    await waitFor(() => expect(mockSave).toHaveBeenCalledWith('item1', 'password'));
  });

  it('clears token when delete clicked', async () => {
    renderWithToast();
    fireEvent.click(screen.getByText('クリア'));
    await waitFor(() => expect(mockDelete).toHaveBeenCalled());
  });
});

