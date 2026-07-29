import React from 'react';
import { motion } from 'framer-motion';

/**
 * Reusable animated container with various preset animations
 */
export default function AnimatedContainer({ 
  children, 
  animation = 'fadeIn', 
  delay = 0,
  className = '',
  ...props 
}) {
  const variants = {
    fadeIn: {
      hidden: { opacity: 0 },
      visible: { 
        opacity: 1,
        transition: { duration: 0.5, delay }
      }
    },
    slideUp: {
      hidden: { opacity: 0, y: 50 },
      visible: { 
        opacity: 1, 
        y: 0,
        transition: { duration: 0.5, delay, type: 'spring', stiffness: 100 }
      }
    },
    slideDown: {
      hidden: { opacity: 0, y: -50 },
      visible: { 
        opacity: 1, 
        y: 0,
        transition: { duration: 0.5, delay, type: 'spring', stiffness: 100 }
      }
    },
    slideLeft: {
      hidden: { opacity: 0, x: 50 },
      visible: { 
        opacity: 1, 
        x: 0,
        transition: { duration: 0.5, delay, type: 'spring', stiffness: 100 }
      }
    },
    slideRight: {
      hidden: { opacity: 0, x: -50 },
      visible: { 
        opacity: 1, 
        x: 0,
        transition: { duration: 0.5, delay, type: 'spring', stiffness: 100 }
      }
    },
    scaleIn: {
      hidden: { opacity: 0, scale: 0.8 },
      visible: { 
        opacity: 1, 
        scale: 1,
        transition: { duration: 0.5, delay, type: 'spring', stiffness: 200 }
      }
    },
    rotateIn: {
      hidden: { opacity: 0, rotate: -10, scale: 0.9 },
      visible: { 
        opacity: 1, 
        rotate: 0, 
        scale: 1,
        transition: { duration: 0.6, delay, type: 'spring', stiffness: 150 }
      }
    },
    float: {
      hidden: { opacity: 0 },
      visible: {
        opacity: 1,
        y: [0, -10, 0],
        transition: {
          opacity: { duration: 0.5, delay },
          y: { duration: 3, repeat: Infinity, ease: 'easeInOut', delay: delay + 0.5 }
        }
      }
    },
    none: {
      hidden: {},
      visible: {}
    }
  };

  return (
    <motion.div
      variants={variants[animation] || variants.fadeIn}
      initial="hidden"
      animate="visible"
      className={className}
      {...props}
    >
      {children}
    </motion.div>
  );
}

/**
 * Stagger children animations
 */
export function AnimatedStaggerContainer({ 
  children, 
  staggerDelay = 0.1,
  className = '',
  ...props 
}) {
  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: staggerDelay
      }
    }
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: { 
      opacity: 1, 
      y: 0,
      transition: { duration: 0.5 }
    }
  };

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className={className}
      {...props}
    >
      {React.Children.map(children, (child, index) => (
        <motion.div key={index} variants={itemVariants}>
          {child}
        </motion.div>
      ))}
    </motion.div>
  );
}

