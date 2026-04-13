import React from 'react'

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <div className="p-6 bg-red-50 border border-red-200 rounded-xl text-center">
          <h2 className="text-red-700 font-semibold mb-2">Something went wrong / Jokin meni pieleen</h2>
          <p className="text-sm text-red-600 mb-4">{this.state.error.message}</p>
          <button
            className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
            onClick={() => this.setState({ error: null })}
          >
            Try again / Yrita uudelleen
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
