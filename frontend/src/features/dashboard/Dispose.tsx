export Dispose(){
{!isAiOpen && (<div className="repo-menu">
                        <p className="text-sm text-green-500 float-right">Semper Repository</p>
                            <div className="flex flex-col gap-3 w-full max-w-2xl">
                                {dummyItems.map((item) => {
                                    const isSelected = selected.has(item.id);

                                    return (
                                        <div
                                            key={item.id}
                                            onClick={() => toggleSelect(item.id)}
                                            className={`flex items-center justify-between p-3 border rounded-xl cursor-pointer transition-all ${
                                                isSelected 
                                                    ? "border-purple-500 bg-purple-50/50" 
                                                    : "border-gray-200 hover:border-gray-300"
                                            }`}
                                        >
                                            {/* Left Side: Repo info & Details */}
                                            <div className="flex items-center gap-4 min-w-0">
                                                <img 
                                                    src={item.avatar_url || `https://dicebear.com{item.owner}`} 
                                                    alt={item.name} 
                                                    className="w-10 h-10 rounded-full bg-gray-100 flex-shrink-0"
                                                />
                                                <div className="min-w-0">
                                                    <p className="font-medium text-gray-900 truncate text-sm sm:text-base">
                                                        {item.full_name}
                                                    </p>
                                                    {isSelected && (
                                                        <span className="text-[10px] bg-purple-100 text-purple-700 px-2 py-0.5 rounded font-bold tracking-wider uppercase mt-1 inline-block">
                                                            Selected
                                                        </span>
                                                    )}
                                                </div>
                                            </div>

                                            {/* Right Side: Action Target aligned perfectly */}
                                            <div className="flex-shrink-0 ml-4">
                                                <div className={`rounded-md cursor-pointer px-4 py-2 text-center h-fit transition-colors min-w-[80px] ${
                                                    isSelected ? "bg-purple-600 text-white" : "bg-green-500 text-white hover:bg-green-600"
                                                }`}>
                                                    <p className="text-sm font-semibold">
                                                        {isSelected ? "Saved" : "Select"}
                                                    </p>
                                                </div>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                    </div>)}, then plugging the functionality?
}