import React, { useState, useEffect } from "react";

interface TypewriterProps {
  text: string;
  speed?: number; // Speed delay in milliseconds per character
}

export const Typewriter: React.FC<TypewriterProps> = ({ text, speed = 20 }) => {
  const [displayedText, setDisplayedText] = useState("");

  useEffect(() => {
    // Reset displayed text whenever a brand-new message arrives
    setDisplayedText("");
    let currentIndex = 0;
    let timerId: any = null;

    const typeCharacter = () => {
      if (currentIndex < text.length) {
        // Use the functional state update to prevent closure tracking traps
        setDisplayedText((prev) => prev + text.charAt(currentIndex));
        currentIndex++;
        timerId = setTimeout(typeCharacter, speed);
      }
    };

    // Kickoff typing sequence
    typeCharacter();

    // Clean up timeout timers when the component unmounts to prevent memory memory leaks
    return () => {
      if (timerId) clearTimeout(timerId);
    };
  }, [text, speed]);

  return <>{displayedText}</>;
};
