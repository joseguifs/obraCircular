import type { InputHTMLAttributes } from 'react'

interface CampoContaProps extends InputHTMLAttributes<HTMLInputElement> {
  id: string
  label: string
  erro?: string
}

export function CampoConta({ label, erro, id, ...props }: CampoContaProps) {
  return (
    <div className="field-group">
      <label htmlFor={id}>{label}</label>
      <div className={`field-box ${erro ? 'field-box--erro' : ''}`}>
        <input
          id={id}
          {...props}
          aria-invalid={Boolean(erro)}
          aria-describedby={erro ? `${id}-erro` : undefined}
        />
      </div>
      {erro && (
        <p className="field-error" id={`${id}-erro`}>
          {erro}
        </p>
      )}
    </div>
  )
}
