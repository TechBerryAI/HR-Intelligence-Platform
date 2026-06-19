import React from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { FEATURES, SOLUTIONS, PRICING_TIERS } from '../constants/landingContent.js'

const fadeUp = {
  hidden: { opacity: 0, y: 32 },
  visible: (i = 0) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.6, delay: i * 0.1, ease: [0.22, 1, 0.36, 1] },
  }),
}

function SectionHeader({ id, title, subtitle }) {
  return (
    <motion.div
      id={id}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, margin: '-80px' }}
      variants={fadeUp}
      className="text-center mb-12 scroll-mt-28"
    >
      <h2 className="text-3xl sm:text-4xl font-bold text-white">{title}</h2>
      {subtitle && <p className="mt-3 text-slate-400 max-w-2xl mx-auto">{subtitle}</p>}
    </motion.div>
  )
}

export default function LandingSections() {
  return (
    <div className="relative z-10 pointer-events-auto bg-[#040c1e]/85 backdrop-blur-sm">
      {/* Features */}
      <section className="px-4 sm:px-6 lg:px-8 py-24 max-w-7xl mx-auto">
        <SectionHeader
          id="features"
          title="Intelligent Features"
          subtitle="AI-native tools that transform how modern organizations hire and manage talent."
        />
        <div className="grid md:grid-cols-3 gap-6">
          {FEATURES.map((f, i) => (
            <motion.div
              key={f.title}
              custom={i}
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true, margin: '-40px' }}
              variants={fadeUp}
              whileHover={{ y: -6 }}
              className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-6 sm:p-8 shadow-[0_8px_32px_rgba(0,0,0,0.2)] ring-1 ring-inset ring-white/5"
            >
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500/30 to-cyan-400/20 flex items-center justify-center mb-4">
                <span className="text-cyan-300 font-bold text-sm">{String(i + 1).padStart(2, '0')}</span>
              </div>
              <h3 className="text-xl font-semibold text-white">{f.title}</h3>
              <p className="mt-2 text-slate-400 text-sm leading-relaxed">{f.description}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Solutions */}
      <section className="px-4 sm:px-6 lg:px-8 py-24 max-w-7xl mx-auto">
        <SectionHeader
          id="solutions"
          title="Solutions for Every Scale"
          subtitle="From startups to enterprise — workforce intelligence that grows with you."
        />
        <div className="grid md:grid-cols-3 gap-6">
          {SOLUTIONS.map((s, i) => (
            <motion.div
              key={s.title}
              custom={i}
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true, margin: '-40px' }}
              variants={fadeUp}
              className="rounded-2xl border border-white/10 bg-slate-900/50 backdrop-blur-xl p-6 sm:p-8"
            >
              <h3 className="text-lg font-semibold text-white">{s.title}</h3>
              <p className="mt-2 text-slate-400 text-sm leading-relaxed">{s.description}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <section className="px-4 sm:px-6 lg:px-8 py-24 max-w-7xl mx-auto">
        <SectionHeader
          id="pricing"
          title="Simple, Transparent Pricing"
          subtitle="Start free. Scale when you're ready."
        />
        <div className="grid md:grid-cols-3 gap-6">
          {PRICING_TIERS.map((tier, i) => (
            <motion.div
              key={tier.name}
              custom={i}
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true, margin: '-40px' }}
              variants={fadeUp}
              className={`rounded-2xl border p-6 sm:p-8 ${
                tier.highlighted
                  ? 'border-cyan-400/40 bg-gradient-to-b from-cyan-500/10 to-blue-500/5 shadow-[0_0_40px_rgba(34,211,238,0.15)]'
                  : 'border-white/10 bg-white/5'
              } backdrop-blur-xl`}
            >
              <h3 className="text-lg font-semibold text-white">{tier.name}</h3>
              <p className="mt-2 text-3xl font-bold text-cyan-300">{tier.price}</p>
              <p className="mt-2 text-sm text-slate-400">{tier.description}</p>
              <ul className="mt-6 space-y-2">
                {tier.features.map((f) => (
                  <li key={f} className="text-sm text-slate-300 flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 shrink-0" />
                    {f}
                  </li>
                ))}
              </ul>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Contact */}
      <section className="px-4 sm:px-6 lg:px-8 py-24 max-w-3xl mx-auto text-center">
        <motion.div
          id="contact"
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          variants={fadeUp}
          className="scroll-mt-28 rounded-3xl border border-white/10 bg-gradient-to-br from-blue-500/10 to-cyan-500/5 backdrop-blur-xl p-10 sm:p-14"
        >
          <h2 className="text-3xl font-bold text-white">Ready to transform your HR?</h2>
          <p className="mt-3 text-slate-400">Get in touch with our team for enterprise solutions and custom deployments.</p>
          <Link
            to="/support/contact"
            className="inline-flex mt-8 px-8 py-3.5 rounded-xl bg-white text-slate-900 font-semibold hover:bg-slate-100 transition-colors"
          >
            Contact Us
          </Link>
        </motion.div>
      </section>

      <footer className="py-10 text-center text-sm text-slate-500 border-t border-white/5">
        © {new Date().getFullYear()} HR Intelligence · Next Generation HR Technology
      </footer>
    </div>
  )
}
