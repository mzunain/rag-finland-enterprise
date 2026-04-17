import React from 'react'
import { getAuthMe, login as apiLogin, clearAccessToken, setAccessToken } from './api'

const AuthContext = React.createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = React.useState(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState('')

  const checkAuth = React.useCallback(async () => {
    try {
      const me = await getAuthMe()
      setUser(me)
      setError('')
    } catch {
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => {
    checkAuth()
  }, [checkAuth])

  const login = async (username, password) => {
    setError('')
    try {
      await apiLogin(username, password)
      await checkAuth()
    } catch (err) {
      setError(err.message || 'Login failed')
      throw err
    }
  }

  const logout = () => {
    clearAccessToken()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, error, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = React.useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
