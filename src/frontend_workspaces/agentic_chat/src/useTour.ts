import { useState, useEffect } from "react";

const TOUR_COMPLETED_KEY = "cuga_tour_completed";

export function useTour() {
  const [isTourActive, setIsTourActive] = useState(false);
  const [hasSeenTour, setHasSeenTour] = useState(false);

  useEffect(() => {
    const tourCompleted = localStorage.getItem(TOUR_COMPLETED_KEY);
    if (tourCompleted === "true") {
      setHasSeenTour(true);
    }
  }, []);

  const startTour = () => {
    setIsTourActive(true);
  };

  const completeTour = () => {
    setIsTourActive(false);
    setHasSeenTour(true);
    localStorage.setItem(TOUR_COMPLETED_KEY, "true");
  };

  const skipTour = () => {
    setIsTourActive(false);
    setHasSeenTour(true);
    localStorage.setItem(TOUR_COMPLETED_KEY, "true");
  };

  const resetTour = () => {
    setHasSeenTour(false);
    localStorage.removeItem(TOUR_COMPLETED_KEY);
    setIsTourActive(true);
  };

  return {
    isTourActive,
    hasSeenTour,
    startTour,
    completeTour,
    skipTour,
    resetTour,
  };
}

