import { render, screen } from '@testing-library/react'
import { OperationProgress, type OperationStep } from './operation-progress'

describe('OperationProgress', () => {
  const mockSteps: OperationStep[] = [
    { id: '1', label: 'Upload files', status: 'completed' },
    { id: '2', label: 'Process documents', status: 'in-progress' },
    { id: '3', label: 'Index content', status: 'pending' },
  ]

  it('renders all steps', () => {
    render(<OperationProgress steps={mockSteps} />)

    expect(screen.getByText('Upload files')).toBeInTheDocument()
    expect(screen.getByText('Process documents')).toBeInTheDocument()
    expect(screen.getByText('Index content')).toBeInTheDocument()
  })

  it('renders title when provided', () => {
    render(<OperationProgress steps={mockSteps} title="Processing Matter" />)

    expect(screen.getByText('Processing Matter')).toBeInTheDocument()
  })

  it('shows completion count', () => {
    render(<OperationProgress steps={mockSteps} title="Processing" />)

    expect(screen.getByText('1/3 completed')).toBeInTheDocument()
  })

  it('shows error message for failed steps', () => {
    const stepsWithError: OperationStep[] = [
      {
        id: '1',
        label: 'Failed step',
        status: 'error',
        errorMessage: 'OCR failed for document',
      },
    ]

    render(<OperationProgress steps={stepsWithError} />)

    expect(screen.getByText('OCR failed for document')).toBeInTheDocument()
  })

  it('applies custom className', () => {
    render(<OperationProgress steps={mockSteps} className="custom-class" />)

    const container = screen.getByRole('group')
    expect(container).toHaveClass('custom-class')
  })

  it('has correct accessibility role', () => {
    render(<OperationProgress steps={mockSteps} title="Progress" />)

    const group = screen.getByRole('group', { name: /progress/i })
    expect(group).toBeInTheDocument()
  })

  it('renders steps as list items', () => {
    render(<OperationProgress steps={mockSteps} />)

    const list = screen.getByRole('list')
    const items = screen.getAllByRole('listitem')

    expect(list).toBeInTheDocument()
    expect(items).toHaveLength(3)
  })

  it('includes screen reader text for step status', () => {
    render(<OperationProgress steps={mockSteps} />)

    // Check that status is included in accessible text
    expect(screen.getByText(/completed/i)).toBeInTheDocument()
    expect(screen.getByText(/in progress/i)).toBeInTheDocument()
    expect(screen.getByText(/pending/i)).toBeInTheDocument()
  })
})
