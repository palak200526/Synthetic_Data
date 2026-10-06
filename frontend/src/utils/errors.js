export function getErrorMessage(err) {
  if (!err) return 'Something went wrong.'

  const data = err?.response?.data

  if (data?.detail) {
    if (typeof data.detail === 'string') return data.detail
    if (Array.isArray(data.detail)) {
      return data.detail
        .map((d) => d?.msg || d?.message || JSON.stringify(d))
        .join(' • ')
    }
  }

  if (data?.message) return data.message
  if (data?.error) return data.error

  if (err.code === 'ERR_NETWORK' || err.message === 'Network Error') {
    return 'Cannot reach the Datrixa backend. Is it running on port 8000?'
  }

    if (err.code === 'ECONNABORTED' || /timeout/i.test(err.message || '')) {
        return (
        'The backend is taking longer than expected. ' +
        'Large datasets and LLM analysis can take a few minutes — ' +
        'try again, and if it keeps failing check the backend logs.'
        )
    }

  return err.message || 'Unexpected error.'
}