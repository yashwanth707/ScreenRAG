/**
 * Drag-and-drop PDF upload component.
 */

import React, { useRef, useState, useCallback } from 'react';
import styles from './ResumeUpload.module.css';

export default function ResumeUpload({ file, onFileSelect }) {
  const inputRef = useRef(null);
  const [isDragOver, setIsDragOver] = useState(false);

  const handleFile = useCallback((selectedFile) => {
    if (!selectedFile) return;

    if (!selectedFile.name.toLowerCase().endsWith('.pdf')) {
      alert('Please upload a PDF file.');
      return;
    }

    onFileSelect(selectedFile);
  }, [onFileSelect]);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setIsDragOver(false);
    const droppedFile = e.dataTransfer.files[0];
    handleFile(droppedFile);
  }, [handleFile]);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragOver(false);
  }, []);

  const handleClick = () => {
    inputRef.current?.click();
  };

  const handleInputChange = (e) => {
    handleFile(e.target.files[0]);
  };

  const formatSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className={styles.wrapper}>
      <label className={styles.label}>Share Your Resume</label>

      <div
        className={`${styles.dropzone} ${isDragOver ? styles.dragOver : ''} ${file ? styles.hasFile : ''}`}
        onClick={handleClick}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        role="button"
        tabIndex={0}
        id="resume-upload-zone"
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf"
          onChange={handleInputChange}
          className={styles.hiddenInput}
          id="resume-file-input"
        />

        {file ? (
          <div className={styles.fileInfo}>
            <div className={styles.fileIcon}>📄</div>
            <div className={styles.fileDetails}>
              <span className={styles.fileName}>{file.name}</span>
              <span className={styles.fileSize}>{formatSize(file.size)}</span>
            </div>
            <button
              className={styles.removeBtn}
              onClick={(e) => {
                e.stopPropagation();
                onFileSelect(null);
              }}
              title="Remove file"
            >
              ✕
            </button>
          </div>
        ) : (
          <div className={styles.placeholder}>
            <div className={styles.uploadIcon}>
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
            </div>
            <p className={styles.placeholderText}>
              <strong>Drop your resume here</strong>
              <br />
              or click to browse
            </p>
            <span className={styles.hint}>PDF files only • Max 10MB</span>
          </div>
        )}
      </div>
    </div>
  );
}
