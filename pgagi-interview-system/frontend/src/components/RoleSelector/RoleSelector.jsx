/**
 * RoleSelector Component
 *
 * Three role cards for interview type selection:
 * - AI/ML Engineer
 * - Backend Engineer
 * - Data Scientist
 *
 * Each card has an icon, title, description, and selected state.
 */

import React from 'react';
import styles from './RoleSelector.module.css';

const ROLES = [
  {
    id: 'ai_ml',
    title: 'AI/ML Engineer',
    description: 'Neural networks, deep learning, model training, MLOps, and optimization',
    icon: '🧠',
    gradient: 'linear-gradient(135deg, #8b5cf6, #06b6d4)',
  },
  {
    id: 'backend',
    title: 'Backend Engineer',
    description: 'System design, APIs, databases, scalability, and distributed systems',
    icon: '⚙️',
    gradient: 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
  },
  {
    id: 'data_science',
    title: 'Data Scientist',
    description: 'Statistics, ML algorithms, data analysis, visualization, and experimentation',
    icon: '📊',
    gradient: 'linear-gradient(135deg, #06b6d4, #10b981)',
  },
];

export default function RoleSelector({ selectedRole, onRoleSelect }) {
  return (
    <div className={styles.wrapper}>
      <label className={styles.label}>Select Target Role</label>
      <div className={styles.grid}>
        {ROLES.map((role) => (
          <button
            key={role.id}
            className={`${styles.card} ${selectedRole === role.id ? styles.selected : ''}`}
            onClick={() => onRoleSelect(role.id)}
            id={`role-card-${role.id}`}
            type="button"
          >
            <div
              className={styles.iconWrapper}
              style={{ background: role.gradient }}
            >
              <span className={styles.icon}>{role.icon}</span>
            </div>
            <h3 className={styles.title}>{role.title}</h3>
            <p className={styles.description}>{role.description}</p>
            {selectedRole === role.id && (
              <div className={styles.checkmark}>✓</div>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
