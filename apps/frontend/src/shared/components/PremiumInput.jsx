import React, { forwardRef, useState } from 'react';
import { FiEye, FiEyeOff } from 'react-icons/fi';

/**
 * Premium input component with autofill animation support.
 * When type="password", shows an eye icon to toggle visibility.
 */
const PremiumInput = forwardRef(({ 
  label,
  error,
  helperText,
  icon: Icon,
  isAutofilled = false,
  className = '',
  wrapperClassName = '',
  as = 'input',
  children,
  type: typeProp = 'text',
  showPasswordToggle = true,
  ...props 
}, ref) => {
  const [isFocused, setIsFocused] = useState(false);
  const [passwordVisible, setPasswordVisible] = useState(false);
  const isPassword = typeProp === 'password';
  const inputType = isPassword && showPasswordToggle && passwordVisible ? 'text' : typeProp;
  const showToggle = isPassword && showPasswordToggle;
  const Component = as === 'select' ? 'select' : as === 'textarea' ? 'textarea' : 'input';

  const labelClass = isFocused
    ? 'block text-sm font-semibold text-[#3AA9FF] mb-2'
    : 'block text-sm font-semibold text-[var(--ei-text-label)] mb-2 org-field-label';

  const fieldClass = `
    premium-input w-full
    ${Icon ? 'pl-11' : ''}
    ${showToggle ? 'pr-11' : ''}
    ${error ? 'border-red-500 focus:border-red-500 focus:ring-red-500' : ''}
    ${isAutofilled ? 'border-blue-500' : ''}
    ${className}
  `.trim();

  return (
    <div className={wrapperClassName}>
      {label && (
        <label className={labelClass}>
          {label}
          {props.required && <span className="text-[#FF6B81] ml-1">*</span>}
        </label>
      )}
      
      <div className="relative">
        {Icon && (
          <div className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--ei-text-muted)] pointer-events-none org-field-icon">
            <Icon className="w-5 h-5" />
          </div>
        )}
        
        <Component
          ref={ref}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          type={as === 'textarea' || as === 'select' ? undefined : inputType}
          className={fieldClass}
          {...props}
        >
          {children}
        </Component>

        {showToggle && (
          <button
            type="button"
            onClick={() => setPasswordVisible((v) => !v)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 focus:outline-none transition-colors p-1 rounded"
            tabIndex={-1}
            aria-label={passwordVisible ? 'Hide password' : 'Show password'}
          >
            {passwordVisible ? <FiEyeOff className="w-5 h-5" /> : <FiEye className="w-5 h-5" />}
          </button>
        )}

        {isAutofilled && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none">
            <div className="w-5 h-5 bg-green-500 rounded-full flex items-center justify-center">
              <svg 
                className="w-3 h-3 text-white" 
                fill="none" 
                strokeLinecap="round" 
                strokeLinejoin="round" 
                strokeWidth="2" 
                viewBox="0 0 24 24" 
                stroke="currentColor"
              >
                <path d="M5 13l4 4L19 7"></path>
              </svg>
            </div>
          </div>
        )}
      </div>
      
      {helperText && !error && (
        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{helperText}</p>
      )}
      
      {error && (
        <p className="mt-1 text-xs text-red-600 dark:text-red-400">
          {error}
        </p>
      )}
    </div>
  );
});

PremiumInput.displayName = 'PremiumInput';

export default PremiumInput;
