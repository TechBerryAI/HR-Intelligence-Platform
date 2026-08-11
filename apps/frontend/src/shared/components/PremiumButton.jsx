import React from 'react';
import { motion } from 'framer-motion';

/**
 * Premium animated button component with micro-interactions
 */
export default function PremiumButton({ 
  children, 
  variant = 'primary',
  size = 'md',
  icon: Icon,
  loading = false,
  disabled = false,
  className = '',
  onClick,
  type = 'button',
  ...props 
}) {
  const baseClasses = 'relative overflow-hidden font-semibold transition-all duration-300 flex items-center justify-center gap-2';
  
  const variants = {
    primary:
      'bg-[var(--ei-btn-primary-from)] hover:brightness-105 text-[var(--ei-btn-primary-text)] shadow-md border border-white/10',
    secondary:
      'bg-slate-100 border border-slate-200 text-slate-900 hover:bg-slate-200 dark:bg-white/[0.08] dark:border-white/15 dark:text-[var(--ei-text-primary)] dark:hover:bg-white/[0.12]',
    outline:
      'border-2 border-[var(--ei-btn-primary-from)] text-[var(--ei-text-primary)] hover:bg-[var(--ei-surface-hover)]',
    ghost: 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800',
    success: 'bg-emerald-600 hover:bg-emerald-500 text-white',
    danger: 'bg-red-600 hover:bg-red-500 text-white',
  };
  
  const sizes = {
    sm: 'text-xs px-3 py-1.5 rounded-lg',
    md: 'text-sm px-6 py-3 rounded-xl',
    lg: 'text-base px-8 py-4 rounded-xl',
  };

  const isDisabled = disabled || loading;

  return (
    <motion.button
      type={type}
      onClick={onClick}
      disabled={isDisabled}
      whileHover={!isDisabled ? { scale: 1.05 } : {}}
      whileTap={!isDisabled ? { scale: 0.95 } : {}}
      className={`${baseClasses} ${variants[variant]} ${sizes[size]} ${className} ${
        isDisabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
      }`}
      {...props}
    >
      {/* Shimmer effect on hover */}
      {!isDisabled && (
        <motion.div
          className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/20 to-transparent"
          whileHover={{
            translateX: '200%',
            transition: { duration: 0.6 }
          }}
        />
      )}

      {/* Content */}
      <span className="relative z-10 flex items-center gap-2">
        {loading ? (
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
            className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full"
          />
        ) : Icon ? (
          <Icon className="w-4 h-4" />
        ) : null}
        {children}
      </span>
    </motion.button>
  );
}

