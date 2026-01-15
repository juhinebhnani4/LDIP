/**
 * CitationsAttentionBanner Component Tests
 *
 * @see Story 10C.3 - Citations Tab List and Act Discovery
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { CitationsAttentionBanner } from './CitationsAttentionBanner';

describe('CitationsAttentionBanner', () => {
  it('renders with issue count', () => {
    render(
      <CitationsAttentionBanner
        issueCount={3}
        missingActsCount={0}
      />
    );

    expect(screen.getByText(/3 CITATIONS NEED ATTENTION/)).toBeInTheDocument();
    expect(screen.getByText(/3 citations have incorrect section references/)).toBeInTheDocument();
  });

  it('renders with missing acts count', () => {
    render(
      <CitationsAttentionBanner
        issueCount={0}
        missingActsCount={2}
      />
    );

    expect(screen.getByText(/2 CITATIONS NEED ATTENTION/)).toBeInTheDocument();
    expect(screen.getByText(/2 Acts are missing/)).toBeInTheDocument();
  });

  it('renders with both issue and missing acts counts', () => {
    render(
      <CitationsAttentionBanner
        issueCount={3}
        missingActsCount={2}
      />
    );

    expect(screen.getByText(/5 CITATIONS NEED ATTENTION/)).toBeInTheDocument();
    expect(screen.getByText(/3 citations have incorrect section references/)).toBeInTheDocument();
    expect(screen.getByText(/2 Acts are missing/)).toBeInTheDocument();
  });

  it('does not render when no issues or missing acts', () => {
    const { container } = render(
      <CitationsAttentionBanner
        issueCount={0}
        missingActsCount={0}
      />
    );

    expect(container).toBeEmptyDOMElement();
  });

  it('uses singular form for 1 citation', () => {
    render(
      <CitationsAttentionBanner
        issueCount={1}
        missingActsCount={0}
      />
    );

    expect(screen.getByText(/1 CITATION NEEDS ATTENTION/)).toBeInTheDocument();
    expect(screen.getByText(/1 citation has incorrect section references/)).toBeInTheDocument();
  });

  it('uses singular form for 1 missing act', () => {
    render(
      <CitationsAttentionBanner
        issueCount={0}
        missingActsCount={1}
      />
    );

    expect(screen.getByText(/1 Act is missing/)).toBeInTheDocument();
  });

  it('renders Review Issues button when callback provided and issues exist', () => {
    const onReviewIssues = vi.fn();

    render(
      <CitationsAttentionBanner
        issueCount={3}
        missingActsCount={0}
        onReviewIssues={onReviewIssues}
      />
    );

    expect(screen.getByRole('button', { name: /review issues/i })).toBeInTheDocument();
  });

  it('does not render Review Issues button when no issues', () => {
    const onReviewIssues = vi.fn();

    render(
      <CitationsAttentionBanner
        issueCount={0}
        missingActsCount={2}
        onReviewIssues={onReviewIssues}
      />
    );

    expect(screen.queryByRole('button', { name: /review issues/i })).not.toBeInTheDocument();
  });

  it('does not render Review Issues button when no callback provided', () => {
    render(
      <CitationsAttentionBanner
        issueCount={3}
        missingActsCount={0}
      />
    );

    expect(screen.queryByRole('button', { name: /review issues/i })).not.toBeInTheDocument();
  });

  it('calls onReviewIssues when Review Issues button is clicked', async () => {
    const user = userEvent.setup();
    const onReviewIssues = vi.fn();

    render(
      <CitationsAttentionBanner
        issueCount={3}
        missingActsCount={0}
        onReviewIssues={onReviewIssues}
      />
    );

    await user.click(screen.getByRole('button', { name: /review issues/i }));

    expect(onReviewIssues).toHaveBeenCalledTimes(1);
  });

  it('renders Upload Missing Acts button when callback provided and missing acts exist', () => {
    const onUploadMissingActs = vi.fn();

    render(
      <CitationsAttentionBanner
        issueCount={0}
        missingActsCount={2}
        onUploadMissingActs={onUploadMissingActs}
      />
    );

    expect(screen.getByRole('button', { name: /upload missing acts/i })).toBeInTheDocument();
  });

  it('does not render Upload Missing Acts button when no missing acts', () => {
    const onUploadMissingActs = vi.fn();

    render(
      <CitationsAttentionBanner
        issueCount={3}
        missingActsCount={0}
        onUploadMissingActs={onUploadMissingActs}
      />
    );

    expect(screen.queryByRole('button', { name: /upload missing acts/i })).not.toBeInTheDocument();
  });

  it('calls onUploadMissingActs when Upload Missing Acts button is clicked', async () => {
    const user = userEvent.setup();
    const onUploadMissingActs = vi.fn();

    render(
      <CitationsAttentionBanner
        issueCount={0}
        missingActsCount={2}
        onUploadMissingActs={onUploadMissingActs}
      />
    );

    await user.click(screen.getByRole('button', { name: /upload missing acts/i }));

    expect(onUploadMissingActs).toHaveBeenCalledTimes(1);
  });

  it('can be collapsed and expanded', async () => {
    const user = userEvent.setup();

    render(
      <CitationsAttentionBanner
        issueCount={3}
        missingActsCount={0}
        onReviewIssues={vi.fn()}
      />
    );

    // Initially expanded - should see Review Issues button
    expect(screen.getByRole('button', { name: /review issues/i })).toBeInTheDocument();

    // Click to collapse
    await user.click(screen.getByRole('button', { name: /collapse attention banner/i }));

    // After collapse, content may be removed from DOM
    await vi.waitFor(() => {
      expect(screen.queryByRole('button', { name: /review issues/i })).not.toBeInTheDocument();
    });

    // Click to expand
    await user.click(screen.getByRole('button', { name: /expand attention banner/i }));

    // After expand, content should be visible again
    expect(screen.getByRole('button', { name: /review issues/i })).toBeInTheDocument();
  });

  it('applies custom className', () => {
    const { container } = render(
      <CitationsAttentionBanner
        issueCount={3}
        missingActsCount={0}
        className="custom-class"
      />
    );

    const collapsibleDiv = container.querySelector('.custom-class');
    expect(collapsibleDiv).toBeInTheDocument();
  });

  it('renders both action buttons when both callbacks provided and issues exist', () => {
    render(
      <CitationsAttentionBanner
        issueCount={3}
        missingActsCount={2}
        onReviewIssues={vi.fn()}
        onUploadMissingActs={vi.fn()}
      />
    );

    expect(screen.getByRole('button', { name: /review issues/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /upload missing acts/i })).toBeInTheDocument();
  });
});
