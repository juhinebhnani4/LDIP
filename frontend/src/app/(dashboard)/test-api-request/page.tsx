'use client'

import { useState } from 'react'
import { useApiRequest } from '@/hooks/useApiRequest'
import { api } from '@/lib/api/client'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

/**
 * Test page for Epic 5: Bounded Request Handling
 *
 * This page exercises:
 * - Story 5.1: Global fetch timeout (30s)
 * - Story 5.2: Slow request feedback (>5s indicator)
 * - Story 5.3: Timeout error message with retry
 * - Story 5.4: Request cleanup on timeout
 */
export default function TestApiRequestPage() {
  const [testResults, setTestResults] = useState<string[]>([])

  // Test hook instance
  const { execute, result, cancel, retry, reset, apiOptions } = useApiRequest<unknown>({
    showToasts: true,
    timeout: 5000, // 5 second timeout for testing
  })

  const addResult = (msg: string) => {
    setTestResults(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`])
  }

  // Test 1: Normal successful request
  const testNormalRequest = async () => {
    addResult('Starting normal request...')
    const data = await execute(() => api.get('/api/matters', apiOptions))
    if (data) {
      addResult('✅ Normal request succeeded')
    } else if (result.error) {
      addResult(`❌ Normal request failed: ${result.error.message}`)
    }
  }

  // Test 2: Slow request (simulated with delay endpoint or just observe)
  const testSlowRequest = async () => {
    addResult('Starting slow request (watch for "Still loading..." toast after 5s)...')
    const data = await execute(() =>
      // This will likely complete fast, but demonstrates the hook setup
      api.get('/api/matters', { ...apiOptions, timeout: 30000 })
    )
    if (data) {
      addResult('✅ Slow request completed')
    } else if (result.error) {
      addResult(`❌ Slow request failed: ${result.error.message}`)
    }
  }

  // Test 3: Cancel request
  const testCancelRequest = async () => {
    addResult('Starting request that will be cancelled...')
    // Start a request
    execute(() => api.get('/api/matters', apiOptions))
    // Cancel it after 100ms
    setTimeout(() => {
      cancel()
      addResult('🛑 Request cancelled')
    }, 100)
  }

  // Test 4: Retry functionality
  const testRetry = async () => {
    if (!result.error) {
      addResult('⚠️ No previous error to retry. Run a failing request first.')
      return
    }
    addResult('Retrying last failed request...')
    const data = await retry()
    if (data) {
      addResult('✅ Retry succeeded')
    } else {
      addResult(`❌ Retry failed: ${result.error?.message}`)
    }
  }

  // Test 5: Reset state
  const testReset = () => {
    reset()
    addResult('🔄 State reset')
  }

  // Test 6: Timeout (using very short timeout via apiOptions override)
  const testTimeout = async () => {
    addResult('Starting request with 1ms timeout (will definitely timeout)...')
    // Pass 1ms timeout directly to api.get to force timeout
    const data = await execute(() =>
      api.get('/api/matters', { timeout: 1 })
    )
    // Check result after a tick
    setTimeout(() => {
      if (!data) {
        addResult(`⏱️ Request timed out as expected`)
      }
    }, 100)
  }

  return (
    <div className="container mx-auto p-6 max-w-4xl">
      <Card>
        <CardHeader>
          <CardTitle>Epic 5: Bounded Request Handling Tests</CardTitle>
          <CardDescription>
            Test the useApiRequest hook functionality for timeout handling, slow request feedback, and retry capability.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Current State */}
          <div className="p-4 bg-muted rounded-lg">
            <h3 className="font-semibold mb-2">Current Hook State:</h3>
            <ul className="text-sm space-y-1">
              <li>Loading: <span className="font-mono">{result.isLoading ? 'true' : 'false'}</span></li>
              <li>Slow Request: <span className="font-mono">{result.isSlowRequest ? 'true' : 'false'}</span></li>
              <li>Has Data: <span className="font-mono">{result.data ? 'true' : 'false'}</span></li>
              <li>Has Error: <span className="font-mono">{result.error ? result.error.message : 'none'}</span></li>
            </ul>
          </div>

          {/* Test Buttons */}
          <div className="flex flex-wrap gap-2">
            <Button onClick={testNormalRequest} disabled={result.isLoading}>
              Test Normal Request
            </Button>
            <Button onClick={testSlowRequest} disabled={result.isLoading} variant="secondary">
              Test Slow Request
            </Button>
            <Button onClick={testCancelRequest} variant="secondary">
              Test Cancel
            </Button>
            <Button onClick={testTimeout} disabled={result.isLoading} variant="destructive">
              Test Timeout (1ms)
            </Button>
            <Button onClick={testRetry} disabled={result.isLoading || !result.error} variant="outline">
              Retry Last
            </Button>
            <Button onClick={testReset} variant="ghost">
              Reset
            </Button>
          </div>

          {/* Test Results Log */}
          <div className="p-4 bg-black text-green-400 rounded-lg font-mono text-sm h-64 overflow-y-auto">
            <div className="mb-2 text-gray-500">--- Test Results ---</div>
            {testResults.length === 0 ? (
              <div className="text-gray-500">Click a test button to begin...</div>
            ) : (
              testResults.map((msg, i) => (
                <div key={i}>{msg}</div>
              ))
            )}
          </div>

          {/* Clear Log */}
          <Button
            onClick={() => setTestResults([])}
            variant="ghost"
            size="sm"
          >
            Clear Log
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
