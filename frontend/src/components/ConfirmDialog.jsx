import React from 'react'

export default function ConfirmDialog({ open, title, message, confirmLabel = 'Confirm', cancelLabel = 'Cancel', onConfirm, onCancel }) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40">
      <div className="w-full max-w-md rounded-xl bg-white border border-slate-200 shadow-xl">
        <div className="p-5 border-b border-slate-200">
          <h3 className="text-base font-semibold text-slate-800">{title}</h3>
          <p className="text-sm text-slate-500 mt-1">{message}</p>
        </div>
        <div className="p-4 flex justify-end gap-2">
          <button className="px-3 py-2 text-sm rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button className="px-3 py-2 text-sm rounded-lg bg-red-600 text-white hover:bg-red-700" onClick={onConfirm}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
