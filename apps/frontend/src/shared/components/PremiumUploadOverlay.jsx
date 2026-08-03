import React, { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { FiFile, FiCheck, FiZap, FiCpu, FiDatabase } from 'react-icons/fi';

/**
 * Premium Upload Overlay - Perfectly Centered & Visible
 * Pass `stageLabel` / `stageIndex` for real Intelligence Engine progress.
 */
export default function PremiumUploadOverlay({
  isVisible,
  type = 'resume',
  stageLabel = null,
  stageIndex = null,
  progressPct = null,
}) {
  const [currentStep, setCurrentStep] = useState(0);
  
  const steps = type === 'resume' 
    ? [
        { icon: FiFile, text: 'Reading Document', color: '#60a5fa', stages: ['cache', 'persist_raw', 'layout', 'text'] },
        { icon: FiCpu, text: 'Detecting Sections', color: '#a78bfa', stages: ['sections', 'deterministic'] },
        { icon: FiDatabase, text: 'Knowledge & Semantics', color: '#f472b6', stages: ['knowledge', 'semantic'] },
        { icon: FiZap, text: 'Validating & Autofill', color: '#4ade80', stages: ['validate', 'persist', 'toon'] },
      ]
    : [
        { icon: FiFile, text: 'Reading Job Description', color: '#60a5fa', stages: ['cache', 'persist_raw', 'layout', 'text'] },
        { icon: FiCpu, text: 'Parsing Requirements', color: '#a78bfa', stages: ['sections', 'deterministic'] },
        { icon: FiDatabase, text: 'Knowledge & Semantics', color: '#f472b6', stages: ['knowledge', 'semantic'] },
        { icon: FiZap, text: 'Preparing Form', color: '#4ade80', stages: ['validate', 'persist', 'toon'] },
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

    // Prefer real stage mapping from Intelligence Engine
    if (stageLabel) {
      const idx = steps.findIndex((s) => (s.stages || []).includes(stageLabel));
      if (idx >= 0) {
        setCurrentStep(idx);
        return;
      }
    }
    if (typeof stageIndex === 'number' && stageIndex >= 0) {
      setCurrentStep(stageIndex % steps.length);
      return;
    }

    // Fallback cosmetic timer only when no real stage events
    const interval = setInterval(() => {
      setCurrentStep((prev) => (prev + 1) % steps.length);
    }, 2000);
    
    return () => clearInterval(interval);
  }, [isVisible, steps.length, stageLabel, stageIndex]);

  const displayText = stageLabel
    ? (stageLabel.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()) +
      (steps[currentStep] ? ` · ${steps[currentStep].text}` : ''))
    : steps[currentStep].text;

  const barPct =
    progressPct != null
      ? Math.max(5, Math.min(100, progressPct))
      : ((currentStep + 1) / steps.length) * 100;

  // Use portal to ensure overlay is always at root level
  const overlayContent = (
    <AnimatePresence>
      {isVisible && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            width: '100vw',
            height: '100vh',
            overflow: 'hidden',
            zIndex: 9999999,
            backgroundColor: 'rgba(0, 0, 0, 0.97)',
            backdropFilter: 'blur(24px)',
            WebkitBackdropFilter: 'blur(24px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
            boxSizing: 'border-box',
            isolation: 'isolate',
            pointerEvents: 'auto',
            margin: 0
          }}
        >
      {/* Background effects */}
      <motion.div
        animate={{ scale: [1, 1.2, 1], opacity: [0.08, 0.15, 0.08] }}
        transition={{ duration: 8, repeat: Infinity }}
        style={{
          position: 'absolute',
          top: '20%',
          left: '20%',
          width: 'min(500px, 40vw)',
          height: 'min(500px, 40vw)',
          maxWidth: '500px',
          maxHeight: '500px',
          background: 'radial-gradient(circle, rgba(139, 92, 246, 0.4) 0%, transparent 70%)',
          borderRadius: '50%',
          filter: 'blur(100px)',
          pointerEvents: 'none',
          overflow: 'hidden'
        }}
      />
      <motion.div
        animate={{ scale: [1.2, 1, 1.2], opacity: [0.08, 0.15, 0.08] }}
        transition={{ duration: 10, repeat: Infinity }}
        style={{
          position: 'absolute',
          bottom: '20%',
          right: '20%',
          width: 'min(500px, 40vw)',
          height: 'min(500px, 40vw)',
          maxWidth: '500px',
          maxHeight: '500px',
          background: 'radial-gradient(circle, rgba(59, 130, 246, 0.4) 0%, transparent 70%)',
          borderRadius: '50%',
          filter: 'blur(100px)',
          pointerEvents: 'none',
          overflow: 'hidden'
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
          width: '100%',
          maxWidth: '420px',
          maxHeight: 'fit-content',
          overflowY: 'visible',
          overflowX: 'hidden',
          backgroundColor: 'rgba(0, 0, 0, 0.95)',
          borderRadius: '28px',
          padding: '22px 24px',
          border: '2px solid transparent',
          backgroundImage: 'linear-gradient(rgba(0, 0, 0, 0.95), rgba(0, 0, 0, 0.95)), linear-gradient(135deg, #8b5cf6, #3b82f6, #06b6d4)',
          backgroundOrigin: 'border-box',
          backgroundClip: 'padding-box, border-box',
          boxShadow: '0 0 0 1px rgba(139, 92, 246, 0.3), 0 25px 100px rgba(0, 0, 0, 0.9), 0 0 80px rgba(139, 92, 246, 0.4)',
          boxSizing: 'border-box',
          marginTop: '-6vh',
          contain: 'layout style paint'
        }}
      >
        {/* Top Icon */}
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '18px' }}>
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
            style={{
              width: '60px',
              height: '60px',
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #8b5cf6 0%, #3b82f6 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 35px rgba(139, 92, 246, 0.6), 0 0 70px rgba(59, 130, 246, 0.3)',
              position: 'relative',
              flexShrink: 0
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
              style: { width: '30px', height: '30px', color: '#ffffff', strokeWidth: 2, flexShrink: 0 }
            })}
          </motion.div>
        </div>

        {/* Status Text */}
        <div style={{ textAlign: 'center', marginBottom: '20px' }}>
          <AnimatePresence mode="wait">
            <motion.h1
              key={currentStep}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.3 }}
              style={{
                fontSize: '19px',
                fontWeight: '800',
                background: `linear-gradient(135deg, ${steps[currentStep].color}, ${steps[currentStep].color}cc)`,
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
                margin: '0 0 6px 0',
                letterSpacing: '-0.3px',
                filter: `drop-shadow(0 0 15px ${steps[currentStep].color}70)`,
                lineHeight: '1.2'
              }}
            >
              {displayText}
            </motion.h1>
          </AnimatePresence>
          <p style={{ 
            fontSize: '12px', 
            color: '#9ca3af', 
            margin: '4px 0 0 0',
            fontWeight: '500',
            lineHeight: '1.4'
          }}>
            {stageLabel ? 'Live pipeline progress' : 'Takes 10-30 seconds'}
          </p>
        </div>

        {/* Progress Steps */}
        <div style={{ marginBottom: '16px', minHeight: 0 }}>
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
                  gap: '12px',
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
                  transition: 'all 0.3s ease',
                  flexShrink: 0
                }}
              >
                <div
                  style={{
                    width: '26px',
                    height: '26px',
                    borderRadius: '50%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                    background: isActive 
                      ? 'linear-gradient(135deg, #8b5cf6, #3b82f6)' 
                      : isCompleted 
                      ? '#22c55e' 
                      : 'rgba(255, 255, 255, 0.07)',
                    boxShadow: isActive 
                      ? '0 0 12px rgba(139, 92, 246, 0.5)' 
                      : isCompleted 
                      ? '0 0 8px rgba(34, 197, 94, 0.4)' 
                      : 'none'
                  }}
                >
                  {isCompleted ? (
                    <FiCheck style={{ width: '15px', height: '15px', color: '#ffffff', strokeWidth: 3 }} />
                  ) : (
                    <step.icon
                      style={{ 
                        width: '13px', 
                        height: '13px', 
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
                    flex: 1,
                    minWidth: 0,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    lineHeight: '1.4'
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
                      borderRadius: '50%',
                      flexShrink: 0
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
          marginBottom: '14px'
        }}>
          <motion.div
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              height: '100%',
              width: `${barPct}%`,
              background: 'linear-gradient(90deg, #8b5cf6 0%, #3b82f6 50%, #06b6d4 100%)',
              backgroundSize: '200% 100%',
              borderRadius: '2.5px',
              boxShadow: '0 0 12px rgba(139, 92, 246, 0.5)'
            }}
            animate={{
              backgroundPosition: ['0% 50%', '200% 50%'],
            }}
            transition={{
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
          padding: '7px 14px',
          borderRadius: '10px',
          background: 'linear-gradient(135deg, rgba(250, 204, 21, 0.08), rgba(251, 191, 36, 0.08))',
          border: '1.5px solid rgba(250, 204, 21, 0.25)',
          boxShadow: '0 0 12px rgba(250, 204, 21, 0.12)'
        }}>
          <FiZap style={{ width: '14px', height: '14px', color: '#fbbf24', flexShrink: 0 }} />
          <span style={{ 
            fontSize: '12px', 
            color: '#fbbf24', 
            fontWeight: '600',
            letterSpacing: '0.2px',
            whiteSpace: 'nowrap'
          }}>
            Powered by AI
          </span>
        </div>
      </motion.div>
    </motion.div>
      )}
    </AnimatePresence>
  );

  // Render in portal to ensure it's always on top
  if (typeof document !== 'undefined') {
    return createPortal(overlayContent, document.body);
  }
  
  return overlayContent;
}
