import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FiFile, FiCheck, FiZap, FiCpu, FiDatabase } from 'react-icons/fi';

/**
 * Premium Upload Overlay - Perfectly Centered & Visible
 */
export default function PremiumUploadOverlay({ isVisible, type = 'resume' }) {
  const [currentStep, setCurrentStep] = useState(0);
  
  const steps = type === 'resume' 
    ? [
        { icon: FiFile, text: 'Reading Resume', color: '#60a5fa' },
        { icon: FiCpu, text: 'Analyzing with AI', color: '#a78bfa' },
        { icon: FiDatabase, text: 'Extracting Skills', color: '#f472b6' },
        { icon: FiZap, text: 'Auto-filling Application', color: '#4ade80' },
      ]
    : [
        { icon: FiFile, text: 'Reading Job Description', color: '#60a5fa' },
        { icon: FiCpu, text: 'Parsing Requirements', color: '#a78bfa' },
        { icon: FiDatabase, text: 'Extracting Details', color: '#f472b6' },
        { icon: FiZap, text: 'Preparing Form', color: '#4ade80' },
      ];

  // Prevent body scroll
  useEffect(() => {
    if (isVisible) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isVisible]);

  useEffect(() => {
    if (!isVisible) {
      setCurrentStep(0);
      return;
    }
    
    const interval = setInterval(() => {
      setCurrentStep((prev) => (prev + 1) % steps.length);
    }, 2000);
    
    return () => clearInterval(interval);
  }, [isVisible, steps.length]);

  if (!isVisible) return null;

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      width: '100vw',
      height: '100vh',
      zIndex: 999999,
      backgroundColor: 'rgba(0, 0, 0, 0.93)',
      backdropFilter: 'blur(20px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '20px'
    }}>
      {/* Background effects */}
      <motion.div
        animate={{ scale: [1, 1.2, 1], opacity: [0.08, 0.15, 0.08] }}
        transition={{ duration: 8, repeat: Infinity }}
        style={{
          position: 'absolute',
          top: '20%',
          left: '20%',
          width: '500px',
          height: '500px',
          background: 'radial-gradient(circle, rgba(139, 92, 246, 0.4) 0%, transparent 70%)',
          borderRadius: '50%',
          filter: 'blur(100px)',
          pointerEvents: 'none'
        }}
      />
      <motion.div
        animate={{ scale: [1.2, 1, 1.2], opacity: [0.08, 0.15, 0.08] }}
        transition={{ duration: 10, repeat: Infinity }}
        style={{
          position: 'absolute',
          bottom: '20%',
          right: '20%',
          width: '500px',
          height: '500px',
          background: 'radial-gradient(circle, rgba(59, 130, 246, 0.4) 0%, transparent 70%)',
          borderRadius: '50%',
          filter: 'blur(100px)',
          pointerEvents: 'none'
        }}
      />

      {/* Main Card */}
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        transition={{ duration: 0.3 }}
        style={{
          position: 'relative',
          zIndex: 10,
          width: '90%',
          maxWidth: '420px',
          backgroundColor: 'rgba(0, 0, 0, 0.95)',
          borderRadius: '28px',
          padding: '28px 26px',
          border: '2px solid transparent',
          backgroundImage: 'linear-gradient(rgba(0, 0, 0, 0.95), rgba(0, 0, 0, 0.95)), linear-gradient(135deg, #8b5cf6, #3b82f6, #06b6d4)',
          backgroundOrigin: 'border-box',
          backgroundClip: 'padding-box, border-box',
          boxShadow: '0 0 0 1px rgba(139, 92, 246, 0.3), 0 25px 100px rgba(0, 0, 0, 0.9), 0 0 80px rgba(139, 92, 246, 0.4)'
        }}
      >
        {/* Top Icon */}
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '20px' }}>
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
            style={{
              width: '64px',
              height: '64px',
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #8b5cf6 0%, #3b82f6 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 35px rgba(139, 92, 246, 0.6), 0 0 70px rgba(59, 130, 246, 0.3)',
              position: 'relative'
            }}
          >
            <motion.div
              animate={{ scale: [1, 1.3, 1], opacity: [0.4, 0, 0.4] }}
              transition={{ duration: 2, repeat: Infinity }}
              style={{
                position: 'absolute',
                inset: '-8px',
                borderRadius: '50%',
                background: 'linear-gradient(135deg, rgba(139, 92, 246, 0.5), rgba(59, 130, 246, 0.5))',
                filter: 'blur(15px)',
                zIndex: -1
              }}
            />
            {React.createElement(steps[currentStep].icon, {
              style: { width: '32px', height: '32px', color: '#ffffff', strokeWidth: 2 }
            })}
          </motion.div>
        </div>

        {/* Status Text */}
        <div style={{ textAlign: 'center', marginBottom: '22px' }}>
          <AnimatePresence mode="wait">
            <motion.h1
              key={currentStep}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.3 }}
              style={{
                fontSize: '20px',
                fontWeight: '800',
                background: `linear-gradient(135deg, ${steps[currentStep].color}, ${steps[currentStep].color}cc)`,
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
                margin: '0 0 6px 0',
                letterSpacing: '-0.3px',
                filter: `drop-shadow(0 0 15px ${steps[currentStep].color}70)`
              }}
            >
              {steps[currentStep].text}
            </motion.h1>
          </AnimatePresence>
          <p style={{ 
            fontSize: '12px', 
            color: '#9ca3af', 
            margin: 0,
            fontWeight: '500'
          }}>
            Takes 10-30 seconds
          </p>
        </div>

        {/* Progress Steps */}
        <div style={{ marginBottom: '18px' }}>
          {steps.map((step, index) => {
            const isActive = index === currentStep;
            const isCompleted = index < currentStep;
            
            return (
              <motion.div
                key={index}
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.07 }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  padding: '10px 12px',
                  marginBottom: index < steps.length - 1 ? '6px' : 0,
                  borderRadius: '12px',
                  backgroundColor: isActive 
                    ? 'rgba(139, 92, 246, 0.12)' 
                    : isCompleted 
                    ? 'rgba(34, 197, 94, 0.1)' 
                    : 'rgba(255, 255, 255, 0.03)',
                  border: `1.5px solid ${isActive 
                    ? 'rgba(139, 92, 246, 0.4)' 
                    : isCompleted 
                    ? 'rgba(34, 197, 94, 0.35)' 
                    : 'rgba(255, 255, 255, 0.07)'}`,
                  boxShadow: isActive ? '0 0 18px rgba(139, 92, 246, 0.2)' : 'none',
                  transition: 'all 0.3s ease'
                }}
              >
                <div
                  style={{
                    width: '28px',
                    height: '28px',
                    borderRadius: '50%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: isActive 
                      ? 'linear-gradient(135deg, #8b5cf6, #3b82f6)' 
                      : isCompleted 
                      ? '#22c55e' 
                      : 'rgba(255, 255, 255, 0.07)',
                    boxShadow: isActive 
                      ? '0 0 12px rgba(139, 92, 246, 0.5)' 
                      : isCompleted 
                      ? '0 0 8px rgba(34, 197, 94, 0.4)' 
                      : 'none',
                    flexShrink: 0
                  }}
                >
                  {isCompleted ? (
                    <FiCheck style={{ width: '16px', height: '16px', color: '#ffffff', strokeWidth: 3 }} />
                  ) : (
                    <step.icon
                      style={{ 
                        width: '14px', 
                        height: '14px', 
                        color: isActive ? '#ffffff' : '#6b7280',
                        strokeWidth: 2
                      }}
                    />
                  )}
                </div>

                <span
                  style={{
                    fontSize: '14px',
                    fontWeight: '600',
                    color: isActive || isCompleted ? '#ffffff' : '#9ca3af',
                    flex: 1
                  }}
                >
                  {step.text}
                </span>

                {isActive && (
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                    style={{
                      width: '16px',
                      height: '16px',
                      border: '2.5px solid rgba(139, 92, 246, 0.2)',
                      borderTopColor: '#8b5cf6',
                      borderRightColor: '#3b82f6',
                      borderRadius: '50%'
                    }}
                  />
                )}
              </motion.div>
            );
          })}
        </div>

        {/* Progress Bar */}
        <div style={{ 
          position: 'relative', 
          width: '100%', 
          height: '5px', 
          backgroundColor: 'rgba(255, 255, 255, 0.07)', 
          borderRadius: '2.5px', 
          overflow: 'hidden',
          marginBottom: '16px'
        }}>
          <motion.div
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              height: '100%',
              background: 'linear-gradient(90deg, #8b5cf6 0%, #3b82f6 50%, #06b6d4 100%)',
              backgroundSize: '200% 100%',
              borderRadius: '2.5px',
              boxShadow: '0 0 12px rgba(139, 92, 246, 0.5)'
            }}
            animate={{
              width: ['0%', '100%'],
              backgroundPosition: ['0% 50%', '200% 50%'],
            }}
            transition={{
              width: { duration: 30, ease: "linear" },
              backgroundPosition: { duration: 2, repeat: Infinity, ease: "linear" },
            }}
          />
        </div>

        {/* AI Badge */}
        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center', 
          gap: '7px',
          padding: '8px 14px',
          borderRadius: '10px',
          background: 'linear-gradient(135deg, rgba(250, 204, 21, 0.08), rgba(251, 191, 36, 0.08))',
          border: '1.5px solid rgba(250, 204, 21, 0.25)',
          boxShadow: '0 0 12px rgba(250, 204, 21, 0.12)'
        }}>
          <FiZap style={{ width: '14px', height: '14px', color: '#fbbf24' }} />
          <span style={{ 
            fontSize: '12px', 
            color: '#fbbf24', 
            fontWeight: '600',
            letterSpacing: '0.2px'
          }}>
            Powered by AI
          </span>
        </div>
      </motion.div>
    </div>
  );
}
