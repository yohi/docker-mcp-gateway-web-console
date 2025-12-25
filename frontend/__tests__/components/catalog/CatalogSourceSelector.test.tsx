import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import CatalogSourceSelector from '../../../components/catalog/CatalogSourceSelector';
import { CATALOG_SOURCES, CatalogSourceId } from '../../../lib/constants/catalogSources';

describe('CatalogSourceSelector', () => {
    it('renders all preset options (docker and official)', () => {
        render(
            <CatalogSourceSelector
                selectedSource="docker"
                onSourceChange={jest.fn()}
            />
        );

        // Docker MCP Catalog と Official MCP Registry の選択肢が表示される
        expect(screen.getByRole('combobox')).toBeInTheDocument();

        // 選択肢が両方存在することを確認
        const select = screen.getByRole('combobox');
        const options = select.querySelectorAll('option');
        expect(options.length).toBe(CATALOG_SOURCES.length);

        CATALOG_SOURCES.forEach((source) => {
            expect(screen.getByRole('option', { name: source.label })).toBeInTheDocument();
        });
    });

    it('shows docker as selected when selectedSource is docker', () => {
        render(
            <CatalogSourceSelector
                selectedSource="docker"
                onSourceChange={jest.fn()}
            />
        );

        const select = screen.getByRole('combobox') as HTMLSelectElement;
        expect(select.value).toBe('docker');
    });

    it('shows official as selected when selectedSource is official', () => {
        render(
            <CatalogSourceSelector
                selectedSource="official"
                onSourceChange={jest.fn()}
            />
        );

        const select = screen.getByRole('combobox') as HTMLSelectElement;
        expect(select.value).toBe('official');
    });

    it('calls onSourceChange when selection changes', () => {
        const mockOnSourceChange = jest.fn();
        render(
            <CatalogSourceSelector
                selectedSource="docker"
                onSourceChange={mockOnSourceChange}
            />
        );

        const select = screen.getByRole('combobox');
        fireEvent.change(select, { target: { value: 'official' } });

        expect(mockOnSourceChange).toHaveBeenCalledTimes(1);
        expect(mockOnSourceChange).toHaveBeenCalledWith('official');
    });

    it('does not provide free-form URL input', () => {
        render(
            <CatalogSourceSelector
                selectedSource="docker"
                onSourceChange={jest.fn()}
            />
        );

        // text input がないことを確認（Requirements 5.3）
        expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    });

    it('applies consistent styling with existing UI', () => {
        render(
            <CatalogSourceSelector
                selectedSource="docker"
                onSourceChange={jest.fn()}
            />
        );

        const select = screen.getByRole('combobox');
        // Tailwind CSS クラスが適用されていることを確認
        expect(select.className).toMatch(/border/);
        expect(select.className).toMatch(/rounded/);
    });

    it('has correct accessible labels', () => {
        render(
            <CatalogSourceSelector
                selectedSource="docker"
                onSourceChange={jest.fn()}
            />
        );

        // ラベルが存在し、セレクタと紐付けられている
        expect(screen.getByLabelText(/カタログソース/i)).toBeInTheDocument();
    });

    it('renders with data-testid for integration testing', () => {
        render(
            <CatalogSourceSelector
                selectedSource="docker"
                onSourceChange={jest.fn()}
            />
        );

        expect(screen.getByTestId('catalog-source-selector')).toBeInTheDocument();
    });
});
