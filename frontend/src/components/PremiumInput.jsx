import React, { forwardRef, useState } from 'react';
import { motion } from 'framer-motion';
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

  return (
    <div className={wrapperClassName}>
      {label && (
        <motion.label 
          className="block text-sm font-medium text-zinc-300 mb-2"
          animate={isFocused ? { color: '#a855f7' } : { color: '#d4d4d8' }}
        >
          {label}
          {props.required && <span className="text-red-400 ml-1">*</span>}
        </motion.label>
      )}
      
      <div className="relative">
        {Icon && (
          <div className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500 z-10">
            <Icon className="w-5 h-5" />
          </div>
        )}
        
        {as === 'input' || as === 'textarea' ? (
          <motion.div
            animate={isAutofilled ? {
              borderColor: ['#8b5cf6', '#6366f1', '#8b5cf6'],
            } : {}}
            transition={{ duration: 1.5 }}
            className="relative"
          >
            <Component
              ref={ref}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              type={as === 'textarea' ? undefined : inputType}
              className={`
                premium-input w-full
                ${Icon ? 'pl-11' : 'pl-3'}
                ${showToggle ? 'pr-11' : ''}
                ${error ? 'border-red-500 focus:border-red-400' : ''}
                ${isAutofilled ? 'autofill-animation border-purple-500' : ''}
                ${className}
              `}
              {...props}
            />
            {showToggle && (
              <button
                type="button"
                onClick={() => setPasswordVisible((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 z-10 text-zinc-500 hover:text-zinc-300 focus:outline-none focus:text-white transition-colors p-1 rounded"
                tabIndex={-1}
                aria-label={passwordVisible ? 'Hide password' : 'Show password'}
              >
                {passwordVisible ? <FiEyeOff className="w-5 h-5" /> : <FiEye className="w-5 h-5" />}
              </button>
            )}
          </motion.div>
        ) : (
          <Component
            ref={ref}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            className={`
              premium-input w-full
              ${Icon ? 'pl-11' : 'pl-3'}
              ${error ? 'border-red-500 focus:border-red-400' : ''}
              ${className}
            `}
            style={{
              color: '#f3f4f6',
              ...(props.style || {})
            }}
            {...props}
          >
            {children}
          </Component>
        )}
        
        {isAutofilled && (
          <motion.div
            initial={{ opacity: 0, x: 10 }}
            animate={{ opacity: 1, x: 0 }}
            className="absolute right-3 top-1/2 -translate-y-1/2 z-10"
          >
            <motion.div
              animate={{
                scale: [1, 1.2, 1],
              }}
              transition={{ duration: 0.5 }}
              className="w-5 h-5 bg-green-500 rounded-full flex items-center justify-center"
            >
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
            </motion.div>
          </motion.div>
        )}
      </div>
      
      {helperText && !error && (
        <p className="mt-1 text-xs text-zinc-400">{helperText}</p>
      )}
      
      {error && (
        <motion.p
          initial={{ opacity: 0, y: -5 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-1 text-xs text-red-400"
        >
          {error}
        </motion.p>
      )}
    </div>
  );
});

PremiumInput.displayName = 'PremiumInput';

export default PremiumInput;

