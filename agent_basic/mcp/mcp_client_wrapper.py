import os
import asyncio
import sys
import logging
import traceback 
import google.generativeai as genai
from typing import Any, Dict, List, Optional  # Add this line
from datetime import datetime
from mcp.client import ClientSession, StdioServerParameters, stdio_client
from dotenv import load_dotenv
# In mcp_client_wrapper.py
from config import Config
import traceback  # Add this for better error reporting
from botbuilder.schema import Activity, ActivityTypes, HeroCard
from botbuilder.core import CardFactory


class ExecutionHistory:
    def __init__(self):
        self.plan = None
        self.steps = []
        self.final_answer = None
        self.user_query = None
        self.tools_description = None

class MCPClientWrapper:
    def __init__(self):
        self.math_session = None
        self.gmail_session = None
        self.tools = []
        self.logger = logging.getLogger(__name__)
        self.model = None
        self.execution_history = ExecutionHistory()
        self.message_queue = asyncio.Queue()
        self.is_running = False
        self.current_task = None
        self.update_interval = 2  # seconds
        self.max_iterations = Config.MAX_ITERATIONS
        
        # Configure logging
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(funcName)20s() %(message)s',
            handlers=[
                logging.FileHandler('mcp_client.log', mode='w'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        # Initialize LLM
        self._initialize_llm()
        
    def _initialize_llm(self):
        """Initialize the LLM (Gemini) configuration"""
        load_dotenv()
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")
            
        self.logger.info("Configuring Gemini API...")
        try:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(Config.MODEL_NAME)
            self.logger.info("Gemini API configured successfully")
        except Exception as e:
            self.logger.error(f"Error configuring Gemini API: {str(e)}")
            raise
            
    async def generate_with_timeout(self, prompt, timeout=Config.TIMEOUT_SECONDS):
        """Generate content with timeout using LLM"""
        self.logger.info("Starting LLM generation...")
        try:
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self.model.generate_content(contents=prompt)
                ),
                timeout=timeout
            )
            self.logger.info("LLM generation completed")
            return response
        except asyncio.TimeoutError:
            self.logger.error("LLM generation timed out!")
            raise
        except Exception as e:
            self.logger.error(f"Error in LLM generation: {e}")
            raise

    async def initialize(self):
        """Initialize MCP servers and tools"""
        try:
            # Initialize server parameters
            math_server_params = StdioServerParameters(
                command="python",
                args=["mcp/mcp_server.py"]
            )
            
            gmail_server_params = StdioServerParameters(
                command="python",
                args=[
                    "mcp/gmail-mcp-server/src/gmail/server.py",
                    "--creds-file-path=.google/client_creds.json",
                    "--token-path=.google/app_tokens.json"
                ]
            )
            
            self.logger.info("Establishing connection to MCP servers...")
            self.logger.debug(f"Math server params: {math_server_params}")
            self.logger.debug(f"Gmail server params: {gmail_server_params}")
            
            # First, await the stdio_client calls
            math_connection = await stdio_client(math_server_params)
            gmail_connection = await stdio_client(gmail_server_params)
            
            math_read, math_write = math_connection
            gmail_read, gmail_write = gmail_connection
            
            self.logger.info("Connections established, creating sessions...")
            
            # Create and initialize sessions
            self.math_session = ClientSession(math_read, math_write)
            self.gmail_session = ClientSession(gmail_read, gmail_write)
            
            # Initialize sessions
            self.logger.debug("Initializing math session...")
            await self.math_session.initialize()
            self.logger.debug("Initializing gmail session...")
            await self.gmail_session.initialize()
            
            # Get tools from math server
            self.logger.debug("Fetching tools from math server...")
            tools_result = await self.math_session.list_tools()
            self.logger.debug(f"Math tools result: {tools_result}")
            
            math_tools = tools_result.get('tools', [])  # Use .get() instead of attribute access
            self.logger.debug(f"Math tools: {math_tools}")
            
            for tool in math_tools:
                tool.server_session = self.math_session
                
            # Get tools from gmail server
            self.logger.debug("Fetching tools from gmail server...")
            tools_result = await self.gmail_session.list_tools()
            self.logger.debug(f"Gmail tools result: {tools_result}")
            
            gmail_tools = tools_result.get('tools', [])  # Use .get() instead of attribute access
            self.logger.debug(f"Gmail tools: {gmail_tools}")
            
            for tool in gmail_tools:
                tool.server_session = self.gmail_session
                
            # Combine tools
            self.tools = math_tools + gmail_tools
            self.logger.debug(f"Combined tools: {self.tools}")
            
            # Create tools description for LLM
            await self._create_tools_description()
            
            # Start the event loop only after successful initialization
            self.is_running = True
            # Create the processing loop task
            self.processing_task = asyncio.create_task(self.start_processing_loop())
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing MCP client: {str(e)}")
            self.logger.error(f"Stack trace: {traceback.format_exc()}")
            return False
            
    async def _create_tools_description(self):
        """Create description of available tools for LLM"""
        try:
            tools_description = []
            for i, tool in enumerate(self.tools):
                try:
                    params = tool.inputSchema
                    desc = getattr(tool, 'description', 'No description available')
                    name = getattr(tool, 'name', f'tool_{i}')
                    
                    if 'properties' in params:
                        param_details = []
                        for param_name, param_info in params['properties'].items():
                            param_type = param_info.get('type', 'unknown')
                            param_details.append(f"{param_name}: {param_type}")
                        params_str = ', '.join(param_details)
                    else:
                        params_str = 'no parameters'
                        
                    tool_desc = f"{i+1}. {name}({params_str}) - {desc}"
                    tools_description.append(tool_desc)
                except Exception as e:
                    self.logger.error(f"Error processing tool {i}: {e}")
                    tools_description.append(f"{i+1}. Error processing tool")
                    
            self.execution_history.tools_description = "\n".join(tools_description)
            
        except Exception as e:
            self.logger.error(f"Error creating tools description: {e}")
            self.execution_history.tools_description = "Error loading tools"
            
    async def process_query(self, query: str) -> str:
        """Process a query using LLM and available tools"""
        try:
            # Update execution history
            self.execution_history.user_query = query
            
            # Create system prompt
            system_prompt = Config.SYSTEM_PROMPT.format(
                tools_description=self.execution_history.tools_description,
                execution_history=self.execution_history
            )
            
            # Generate plan
            self.logger.info("Generating plan...")
            plan_prompt = f"{system_prompt}"
            plan_response = await self.generate_with_timeout(plan_prompt)
            self.execution_history.plan = plan_response.text
            
            # Execute plan
            self.logger.info("Executing plan...")
            execution_prompt = f"{system_prompt}\n\nPlan: {self.execution_history.plan}\n\nExecute the plan:"
            execution_response = await self.generate_with_timeout(execution_prompt)
            
            # Parse and execute tool calls
            tool_calls = self._parse_tool_calls(execution_response.text)
            for tool_call in tool_calls:
                result = await self.execute_command(tool_call['name'], tool_call['params'])
                self.execution_history.steps.append({
                    'tool': tool_call['name'],
                    'params': tool_call['params'],
                    'result': result
                })
                
            # Generate final answer
            final_prompt = f"{system_prompt}\n\nResults: {self.execution_history.steps}\n\nProvide final answer:"
            final_response = await self.generate_with_timeout(final_prompt)
            self.execution_history.final_answer = final_response.text
            
            return self.execution_history.final_answer
            
        except Exception as e:
            self.logger.error(f"Error processing query: {str(e)}")
            return f"Error processing query: {str(e)}"
            
    def _parse_tool_calls(self, llm_response: str) -> list:
        """Parse tool calls from LLM response"""
        # Implement parsing logic based on your LLM's output format
        # This is a placeholder implementation
        tool_calls = []
        # Add parsing logic here
        return tool_calls
            
    async def execute_command(self, command_name: str, params: dict = None) -> Any:
        """Execute a specific command with parameters"""
        try:
            tool = next((t for t in self.tools if t.name == command_name), None)
            if not tool:
                raise ValueError(f"Tool {command_name} not found")
                
            self.logger.info(f"Executing {command_name} with params: {params}")
            result = await tool.execute(params or {})
            self.logger.info(f"Command result: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing command {command_name}: {str(e)}")
            return f"Error: {str(e)}"

    async def start_processing_loop(self):
        """Main event loop for processing messages"""
        self.logger.info("Starting message processing loop...")
        while self.is_running:
            try:
                # Wait for next message
                self.logger.info("Waiting for next message...")
                task_data = await self.message_queue.get()
                
                # Process the task with iterations
                await self._process_task_with_iterations(task_data)
                
                # Mark task as complete
                self.message_queue.task_done()
                
            except Exception as e:
                self.logger.error(f"Error in processing loop: {str(e)}")
                continue

    async def _process_task_with_iterations(self, task_data):
        """Process task with iteration loop and updates"""
        query = task_data['query']
        turn_context = task_data['turn_context']
        iteration = 0
        
        try:
            # Reset execution history for new task
            self.execution_history = ExecutionHistory()
            self.execution_history.user_query = query
            
            # Send initial status
            await self._send_status_update(
                turn_context,
                "Starting task processing...",
                is_initial=True
            )
            
            while iteration < self.max_iterations:
                self.logger.info(f"Processing iteration {iteration + 1}/{self.max_iterations}")
                
                # Create system prompt for this iteration
                system_prompt = Config.SYSTEM_PROMPT.format(
                    tools_description=self.execution_history.tools_description,
                    execution_history=self.execution_history
                )
                
                # Generate and execute plan for this iteration
                plan_response = await self.generate_with_timeout(system_prompt)
                self.execution_history.plan = plan_response.text
                
                # Send status update about plan
                await self._send_status_update(
                    turn_context,
                    f"Iteration {iteration + 1}: Generated plan",
                    include_plan=True
                )
                
                # Execute tools for this iteration
                execution_response = await self.generate_with_timeout(
                    f"{system_prompt}\n\nPlan: {self.execution_history.plan}\n\nExecute the plan:"
                )
                
                tool_calls = self._parse_tool_calls(execution_response.text)
                for tool_call in tool_calls:
                    # Execute tool and record result
                    result = await self.execute_command(
                        tool_call['name'], 
                        tool_call['params']
                    )
                    self.execution_history.steps.append({
                        'iteration': iteration + 1,
                        'tool': tool_call['name'],
                        'params': tool_call['params'],
                        'result': result
                    })
                    
                    # Send status update after each tool execution
                    await self._send_status_update(
                        turn_context,
                        f"Iteration {iteration + 1}: Executed {tool_call['name']}",
                        include_steps=True
                    )
                
                # Check if task is complete
                if await self._is_task_complete():
                    await self._send_final_update(turn_context)
                    break
                
                iteration += 1
                await asyncio.sleep(self.update_interval)
            
        except Exception as e:
            self.logger.error(f"Error processing task: {str(e)}")
            await self._send_error_update(turn_context, str(e))

    async def _send_status_update(self, turn_context, status, 
                                is_initial=False, include_plan=False, 
                                include_steps=False):
        """Send comprehensive status update"""
        text = [status]
        
        if include_plan and self.execution_history.plan:
            text.append(f"\nCurrent Plan:\n{self.execution_history.plan}")
            
        if include_steps and self.execution_history.steps:
            text.append("\nExecuted Steps:")
            for step in self.execution_history.steps:
                text.append(f"- Iteration {step['iteration']}: {step['tool']} → {step['result']}")
        
        card = HeroCard(
            title="🤖 Agent Processing" if not is_initial else "🚀 Starting Processing",
            subtitle=status,
            text="\n".join(text)
        )
        
        await turn_context.send_activity(
            Activity(
                type=ActivityTypes.message,
                attachments=[CardFactory.hero_card(card)]
            )
        )

    async def _is_task_complete(self):
        """Check if task is complete based on execution history"""
        # Implement your task completion logic here
        # For example, check if final answer is achieved
        return False  # Placeholder

    async def _send_final_update(self, turn_context):
        """Send final update after task completion"""
        # Implement final update logic here
        pass

    async def _send_error_update(self, turn_context, error_message):
        """Send error update after task failure"""
        # Implement error update logic here
        pass