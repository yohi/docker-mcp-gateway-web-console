import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import OAuthModal from '../../../components/catalog/OAuthModal';
import { initiateOAuth, exchangeOAuth } from '../../../lib/api/oauth';

jest.mock('../../../lib/api/oauth', () => ({
  initiateOAuth: jest.fn(),
  exchangeOAuth: jest.fn(),
  refreshOAuth: jest.fn(),
}));

const mockItem = {
  id: 'server-x',
  name: 'Server X',
  description: 'desc',
  category: 'cat',
  docker_image: 'img',
  default_env: {},
  required_envs: [],
  required_secrets: [],
  vendor: 'v',
  icon_url: '',
  required_scopes: ['repo:read'],
  verify_signatures: true,
};

describe('OAuthModal', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('starts OAuth flow and displays auth URL/state', async () => {
    (initiateOAuth as jest.Mock).mockResolvedValue({
      auth_url: 'https://provider/authorize',
      state: 'state-123',
      required_scopes: ['repo:read'],
    });

    render(<OAuthModal isOpen item={mockItem} onClose={() => {}} />);

    fireEvent.click(screen.getByRole('button', { name: '認可を開始' }));

    await waitFor(() => {
      expect(initiateOAuth).toHaveBeenCalledWith(
        expect.objectContaining({
          serverId: mockItem.id,
          scopes: mockItem.required_scopes,
          codeChallengeMethod: 'S256',
        })
      );
    });

    expect(await screen.findByText('https://provider/authorize')).toBeInTheDocument();
    expect(screen.getByText('state-123')).toBeInTheDocument();
  });

  it('exchanges code using stored verifier', async () => {
    (initiateOAuth as jest.Mock).mockResolvedValue({
      auth_url: 'https://provider/authorize',
      state: 'state-123',
      required_scopes: ['repo:read'],
    });
    (exchangeOAuth as jest.Mock).mockResolvedValue({
      credential_key: 'cred-1',
      scope: ['repo:read'],
      status: 'connected',
      expires_at: '2025-12-10T00:00:00Z',
    });

    render(<OAuthModal isOpen item={mockItem} onClose={() => {}} />);

    fireEvent.click(screen.getByRole('button', { name: '認可を開始' }));
    await screen.findByText('https://provider/authorize');

    fireEvent.change(screen.getByLabelText('認可コード'), { target: { value: 'code-abc' } });
    fireEvent.click(screen.getByRole('button', { name: 'コードを交換' }));

    await waitFor(() => {
      expect(exchangeOAuth).toHaveBeenCalledWith(
        expect.objectContaining({
          code: 'code-abc',
          serverId: mockItem.id,
          state: 'state-123',
          codeVerifier: expect.any(String),
        })
      );
    });

    expect(await screen.findByText('cred-1')).toBeInTheDocument();
  });
});
