import apiClient from './client.js'

export const reportApi = {
  get: (params = {}) =>
    apiClient.get('/report', {
      params,
    }),

  generate: (resultId, format = 'json') =>
    apiClient.post('/report', {
      result_id: Number(resultId),
      format,
    }),

  download: async (params = {}) => {
    try {
      const res = await apiClient.get('/download', {
        params: {
          type: 'report',
          ...params,
        },
        responseType: 'blob',
        timeout: 5 * 60 * 1000,
      })

      const ct = res.headers?.['content-type'] || ''

      const disposition = res.headers?.['content-disposition'] || ''
      let fileName = null
      const utf8 = /filename\*=UTF-8''([^;\r\n]+)/i.exec(disposition)
      if (utf8 && utf8[1]) {
        try {
          fileName = decodeURIComponent(utf8[1].trim())
        } catch {
          fileName = utf8[1].trim()
        }
      }
      if (!fileName) {
        const plain = /filename="?([^";\r\n]+)"?/i.exec(disposition)
        if (plain && plain[1]) fileName = plain[1].trim()
      }
      if (!fileName) {
        const fmt = params.format || 'json'
        fileName = `evaluation_report.${fmt}`
      }

      const blob = new Blob([res.data], { type: ct || 'application/octet-stream' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = fileName
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)

      return fileName
    } catch (err) {
      if (err?.response?.data instanceof Blob) {
        try {
          const errText = await err.response.data.text()
          const parsed = JSON.parse(errText)
          throw new Error(parsed.detail || parsed.message || errText)
        } catch (parseErr) {
          if (parseErr.message && !parseErr.message.includes('JSON')) {
            throw parseErr
          }
        }
      }
      throw err
    }
  },
}
