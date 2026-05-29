import { Bot, CheckCheck, Search } from "lucide-react";

export default function Dashboard() {
    return <div>

        <div className="w-full flex pr-4 pl-2">

        {/* <!-- left bar --> */}
        <div className=" xl:mr-0 w-[11.5%] h-full flex flex-col hidden md:block">

            <div className="tabs flex flex-col h-full">
                <div id="project-tabs" className="hidden xl:block">
                    <div
                        style={{ backgroundColor: '#be9ee2' }}
                        className="cursor-pointer w-full px-3 py-2 mt-[27px] rounded-lg  hover:bg-purple-200 hover:text-black flex items-center justify-start gap-3">
                        <CheckCheck className="cursor-pointer" />
                        <p >My Task</p>
                    </div>

                    <div
                        className="cursor-pointer w-full px-3 py-2  rounded-lg hover:bg-purple-200 hover:text-black flex items-center justify-start gap-3">
                        <i className="material-icons-outlined">group</i>
                        <p>Team</p>
                    </div>
                </div>

                {/* <!-- second tab  --> */}
                <div className="top-tabs w-full grid xl:hidden">
                    <p
                        className="cursor-pointer w-full px-3 py-2 mt-[27px] rounded-lg hover:bg-purple-200 bg-purple-300 hover:text-black flex items-center justify-start gap-3">
                        My Task</p>
                    <p
                        className="cursor-pointer w-full px-3 py-2  rounded-lg hover:bg-purple-200 hover:text-black flex items-center justify-start gap-3">
                        Team</p>
                    <p
                        className="cursor-pointer w-full px-3 py-2  rounded-lg hover:bg-purple-200 hover:text-black flex items-center justify-start gap-3">
                        File</p>
                    <p
                        className="cursor-pointer w-full px-3 py-2  rounded-lg hover:bg-purple-200 hover:text-black flex items-center justify-start gap-3">
                        Calendar</p>
                </div>

                {/* <!-- insights --> */}
                <div className="insights mt-8 ml-4 ">
                    <p className="mt-4 mb-4 text-black">Insights</p>
                    <div className="w-full flex gap-2 items-center">
                        <i className="material-icons-outlined">chat</i>
                        <p>Inbox</p>
                        <div className="w-[25px] h-[25px] bg-red-400 rounded-full flex items-center justify-center">
                            <p className="text-sm text-white">18</p>
                        </div>

                    </div>
                </div>

            </div>
            
        </div>

        {/* center, topbar and right bar  */}
        <div className="w-[80%] left-right-container flex-grow">
            {/* topbar */}
            <div className="w-full pt-[10px]">
                <div className="w-full flex items-center gap-6 pl-2 pr-4">

                    {/*  my proj */}
                    <div className="my-proj w-fit hidden md:flex items-center gap-2">
                        <p className="font-bold text-black">Welcome, John</p>
                    </div>

                    {/* <!-- input box parent --> */}
                    <div className="flex justify-between items-center flex-grow">
                        {/* <!-- input box --> */}
                        <div className="w-[60%] xl:w-[72%] relative">
                            <input id="input-search" type="text" placeholder="Search projects, Tasks, etc..."
                                className="pl-4 rounded-xl h-[25px] w-full shadow-lg" />
                            <div id="search-icon">
                                <Search className="w-4 h-4 text-gray-500" />
                            </div>

                            {/* <i class="material-icons-outlined cursor-pointer absolute text-black right-2 top-1">search_outlined</i> */}
                        </div>

                        {/* <!-- chat support icon --> */}
                        <div id="ai-chat-support" className="md:w-[100px] w-fit p-4 mt-auto shadow-md rounded-full cursor-pointer grid items-center justify-center ">
                            <div className="w-full flex justify-center">
                                <Bot className="material-icons-outlined text-[12px]" />
                            </div>
                                <p className="text-[12px] hidden md:flex">Support</p>
                        </div>
                    </div>
                </div>
            </div>

            {/* parent of right nd center bar */}
            <div className="flex mt-4">
                {/* ceenter menu */}
                <div className="h-full w-[72%] flex-grow mt-4 pr-4 pl-2">               
                    {/* repo menu */}

                    <div className="repo-menu">
                        <p className="text-sm text-green-500 float-right">Semper Repository</p>
                    </div>
                    {/* search menu */}
                    <div className="search-menu hidden">
                        <p>Search</p>
                    </div>
                </div>

                {/* right bar */}
                <div className="w-[25%] h-full pl-4 hidden lg:block">
                    right bar placeholder
                </div>  
    </div>
        </div>
            </div>
        </div>
        
}