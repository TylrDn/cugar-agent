import React, { useState, useEffect, useCallback } from "react";
import { X, ChevronLeft, ChevronRight, Check } from "lucide-react";
import "./GuidedTour.css";

export interface TourStep {
  target: string;
  title: string;
  content: string;
  placement?: "top" | "bottom" | "left" | "right";
  highlightPadding?: number;
  beforeShow?: () => void;
  afterShow?: () => void;
}

interface GuidedTourProps {
  steps: TourStep[];
  isActive: boolean;
  onComplete: () => void;
  onSkip: () => void;
}

export function GuidedTour({ steps, isActive, onComplete, onSkip }: GuidedTourProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [tooltipPosition, setTooltipPosition] = useState({ top: 0, left: 0 });
  const [highlightPosition, setHighlightPosition] = useState({ top: 0, left: 0, width: 0, height: 0 });

  const calculatePositions = useCallback(() => {
    if (!isActive || currentStep >= steps.length) return;

    const step = steps[currentStep];
    
    // Support multiple selectors separated by comma
    const selectors = step.target.split(',').map(s => s.trim());
    let targetElement: Element | null = null;
    
    for (const selector of selectors) {
      targetElement = document.querySelector(selector);
      if (targetElement) break;
    }

    if (!targetElement) {
      console.warn(`Tour target not found: ${step.target}`);
      return;
    }

    const rect = targetElement.getBoundingClientRect();
    const padding = step.highlightPadding || 8;

    // Set highlight position
    setHighlightPosition({
      top: rect.top - padding,
      left: rect.left - padding,
      width: rect.width + padding * 2,
      height: rect.height + padding * 2,
    });

    // Calculate tooltip position
    const tooltipWidth = 320;
    const tooltipHeight = 200;
    const spacing = 16;

    let top = 0;
    let left = 0;

    const placement = step.placement || "bottom";

    switch (placement) {
      case "top":
        top = rect.top - tooltipHeight - spacing;
        left = rect.left + rect.width / 2 - tooltipWidth / 2;
        break;
      case "bottom":
        top = rect.bottom + spacing;
        left = rect.left + rect.width / 2 - tooltipWidth / 2;
        break;
      case "left":
        top = rect.top + rect.height / 2 - tooltipHeight / 2;
        left = rect.left - tooltipWidth - spacing;
        break;
      case "right":
        top = rect.top + rect.height / 2 - tooltipHeight / 2;
        left = rect.right + spacing;
        break;
    }

    // Ensure tooltip stays within viewport
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    if (left < spacing) left = spacing;
    if (left + tooltipWidth > viewportWidth - spacing) {
      left = viewportWidth - tooltipWidth - spacing;
    }
    if (top < spacing) top = spacing;
    if (top + tooltipHeight > viewportHeight - spacing) {
      top = viewportHeight - tooltipHeight - spacing;
    }

    setTooltipPosition({ top, left });

    // Scroll element into view if needed
    targetElement.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [isActive, currentStep, steps]);

  useEffect(() => {
    if (isActive) {
      calculatePositions();
      
      // Execute beforeShow callback
      const step = steps[currentStep];
      if (step?.beforeShow) {
        step.beforeShow();
      }

      // Recalculate on window resize
      const handleResize = () => calculatePositions();
      window.addEventListener("resize", handleResize);
      
      // Small delay to ensure DOM is ready
      const timer = setTimeout(calculatePositions, 100);
      
      return () => {
        window.removeEventListener("resize", handleResize);
        clearTimeout(timer);
      };
    }
  }, [isActive, currentStep, calculatePositions, steps]);

  useEffect(() => {
    // Execute afterShow callback
    const step = steps[currentStep];
    if (step?.afterShow && isActive) {
      step.afterShow();
    }
  }, [currentStep, isActive, steps]);

  const handleNext = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep(currentStep + 1);
    } else {
      handleComplete();
    }
  };

  const handlePrevious = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleComplete = () => {
    onComplete();
    setCurrentStep(0);
  };

  const handleSkip = () => {
    onSkip();
    setCurrentStep(0);
  };

  if (!isActive || currentStep >= steps.length) {
    return null;
  }

  const step = steps[currentStep];
  const progress = ((currentStep + 1) / steps.length) * 100;

  return (
    <>
      {/* Backdrop overlay */}
      <div className="tour-overlay" />

      {/* Highlight spotlight */}
      <div
        className="tour-highlight"
        style={{
          top: `${highlightPosition.top}px`,
          left: `${highlightPosition.left}px`,
          width: `${highlightPosition.width}px`,
          height: `${highlightPosition.height}px`,
        }}
      />

      {/* Tooltip */}
      <div
        className="tour-tooltip"
        style={{
          top: `${tooltipPosition.top}px`,
          left: `${tooltipPosition.left}px`,
        }}
      >
        <div className="tour-tooltip-header">
          <div className="tour-step-counter">
            Step {currentStep + 1} of {steps.length}
          </div>
          <button className="tour-close-btn" onClick={handleSkip} title="Skip tour">
            <X size={16} />
          </button>
        </div>

        <div className="tour-tooltip-content">
          <h3 className="tour-tooltip-title">{step.title}</h3>
          <p className="tour-tooltip-text">{step.content}</p>
        </div>

        <div className="tour-tooltip-footer">
          <div className="tour-progress-bar">
            <div className="tour-progress-fill" style={{ width: `${progress}%` }} />
          </div>

          <div className="tour-tooltip-actions">
            <button
              className="tour-btn tour-btn-secondary"
              onClick={handleSkip}
            >
              Skip Tour
            </button>

            <div className="tour-navigation">
              <button
                className="tour-btn tour-btn-icon"
                onClick={handlePrevious}
                disabled={currentStep === 0}
                title="Previous"
              >
                <ChevronLeft size={16} />
              </button>

              <button
                className="tour-btn tour-btn-primary"
                onClick={handleNext}
              >
                {currentStep === steps.length - 1 ? (
                  <>
                    <Check size={16} />
                    Finish
                  </>
                ) : (
                  <>
                    Next
                    <ChevronRight size={16} />
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
